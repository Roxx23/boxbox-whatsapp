import json
import logging
import random
import re
import string
import threading
import time
from datetime import datetime, timedelta, timezone

def _now():
    """Always return UTC time as naive ISO string to match SQLite's strftime('now')."""
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

logger = logging.getLogger(__name__)

_db = None
_message_queue = None


def start_flow_engine(db, message_queue):
    global _db, _message_queue
    _db = db
    _message_queue = message_queue
    t = threading.Thread(target=_engine_loop, daemon=True, name='flow_engine')
    t.start()
    logger.info("Flow engine started")


def enroll_participant(db, flow_id, phone, context_dict, first_step_key):
    # A flow's first content step (the trigger's next_yes) can itself be a
    # 'wait' step -- e.g. Trigger -> Wait 1h -> Send Message. Without this,
    # enroll_flow_participant() stamped next_action_at as "now" regardless of
    # step type, so the very first engine pass (fired immediately below, or
    # the next 15s tick) saw the wait step as already due and skipped straight
    # past it with zero delay. Compute the real due time the same way
    # _advance_to_step() does for every later transition, so entering a wait
    # step behaves identically whether it's the first step or a later one.
    first_step = db.get_flow_step(flow_id, first_step_key) if first_step_key else None
    next_action_at = _next_action_at_for_entering(first_step)
    participant_id = db.enroll_flow_participant(flow_id, phone, context_dict, first_step_key, next_action_at)
    logger.info(f"Flow {flow_id}: enrolled {phone} (participant {participant_id})")
    if participant_id:
        # Fire immediately — don't wait for the 60s engine tick
        threading.Thread(
            target=_process_participant_by_id,
            args=(participant_id,),
            daemon=True,
            name=f'flow_immediate_{participant_id}'
        ).start()
    return participant_id


def _process_participant_by_id(participant_id):
    try:
        participant = _db.get_flow_participant_by_id(participant_id)
        if participant and participant['status'] == 'active':
            _process_participant(participant)
    except Exception as e:
        logger.error(f"Flow engine: immediate processing error for participant {participant_id}: {e}", exc_info=True)


def trigger_immediate_recheck(db, whatsapp_message_id, field, value):
    """Called from WhatsApp webhook handler on read/reply. Updates flow_message status
    and marks participant for immediate re-evaluation (next engine tick within 60s)."""
    flow_msg = db.get_flow_message_by_wamid(whatsapp_message_id)
    if not flow_msg:
        return
    db.update_flow_message_status(whatsapp_message_id, field, value)
    participant = db.get_flow_participant_by_id(flow_msg['flow_participant_id'])
    if not participant or participant['status'] != 'active':
        return
    step = db.get_flow_step(participant['flow_id'], participant['current_step_key'])
    if step and step['step_type'] == 'condition':
        db.update_participant_next_action(participant['id'], _now())
        logger.debug(f"Flow engine: fast-path recheck queued for participant {participant['id']}")


def get_flow_first_step_key(db, flow_id):
    """Return the step_key of the first non-trigger step (trigger node's output)."""
    steps = db.get_flow_steps(flow_id)
    trigger = next((s for s in steps if s['step_type'] == 'trigger'), None)
    if trigger:
        return trigger.get('next_yes')
    return None


def _format_currency(value):
    """'1299.00' -> '₹1299', '1299.50' -> '₹1299.50'. Matches the ₹-prefix
    convention used by the legacy automation sends (app.py)."""
    if not value:
        return ''
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return f"₹{value}"
    if amount == int(amount):
        return f"₹{int(amount)}"
    return f"₹{amount:.2f}"


def build_trigger_context(trigger_type, data):
    """Build context dict from Shopify webhook payload for a given trigger type."""
    ctx = {}
    if trigger_type in ('order_confirmation', 'fulfillment', 'order_cancelled', 'order_refunded'):
        # Plumbing, not a user-facing template variable -- deliberately left out
        # of CTX_KEYS_BY_TRIGGER in flow_editor.html. shopify_orders.shopify_order_id
        # stores this same raw Shopify order id, NOT the '#F1{order_number}'
        # display format below -- the 'order fulfilled?' condition type looks
        # orders up by this key, and a naive match against order_number would
        # silently fail.
        ctx['shopify_order_id'] = str(data.get('id', ''))
        customer = data.get('customer') or {}
        ctx['first_name'] = customer.get('first_name') or customer.get('email', '').split('@')[0]
        raw_num = str(data.get('order_number', ''))
        ctx['order_number'] = f"#F1{raw_num}"
        ctx['items'] = _format_items_from_line_items(data.get('line_items', []))
        ctx['total'] = _format_currency(data.get('total_price', ''))
        # Raw line items (not the formatted 'items' string) — needed to resolve a
        # product image for an IMAGE-header template's 'auto' source at send time.
        ctx['line_items'] = data.get('line_items', [])
        if trigger_type == 'fulfillment':
            fulfillments = data.get('fulfillments', [])
            tracking = ''
            if fulfillments:
                tracking = fulfillments[0].get('tracking_url') or ''
            ctx['tracking_url'] = tracking
            ctx['courier_name'] = data.get('courier_name', '')
            ctx['tracking_number'] = data.get('tracking_number', '')
        elif trigger_type == 'order_cancelled':
            # Shopify's orders/cancelled payload carries this directly (values:
            # customer/inventory/fraud/declined/other) -- lets a cancellation
            # win-back flow gate on it via the 'cancel_reason_is' condition,
            # e.g. skip sending a save-the-sale discount for fraud/declined.
            ctx['cancel_reason'] = data.get('cancel_reason') or ''
        elif trigger_type == 'order_refunded':
            # 'total' above is the ORDER's original total (from the stored
            # shopify_orders row -- see shopify_order_refunded() in app.py),
            # not what was actually refunded. refunds/create's payload carries
            # the real amount across a transactions[] array (each with its own
            # 'amount'), which correctly handles a partial refund -- summing
            # them is the actual refunded total. shopify_order_refunded()
            # stashes the raw refund payload as data['refund'] before calling
            # this. _format_currency('') / a 0 sum both fall through to '' via
            # its own falsy-value guard, so a refund with no transactions data
            # (shouldn't happen, but don't assume) leaves this blank rather
            # than claiming ₹0 was refunded.
            refund = data.get('refund') or {}
            transactions = refund.get('transactions') or []
            total_refunded = sum(float(t.get('amount') or 0) for t in transactions)
            ctx['refund_amount'] = _format_currency(total_refunded)
    elif trigger_type == 'abandoned_cart':
        customer = data.get('customer') or {}
        ctx['first_name'] = customer.get('first_name') or (data.get('email', '').split('@')[0])
        ctx['items'] = _format_items_from_line_items(data.get('line_items', []))
        ctx['total'] = _format_currency(data.get('total_price', ''))
        ctx['cart_url'] = data.get('abandoned_checkout_url', '')
        ctx['line_items'] = data.get('line_items', [])
    elif trigger_type == 'customer_created':
        customer = data.get('customer') or data  # data itself might be the customer for some webhooks
        ctx['first_name'] = customer.get('first_name') or customer.get('email', '').split('@')[0]
        ctx['email'] = customer.get('email', '')
        ctx['phone'] = customer.get('phone', '')
    return ctx


def _format_items_from_line_items(line_items, max_items=3):
    parts = []
    for item in line_items[:max_items]:
        name = item.get('title', '')
        variant = item.get('variant_title') or ''
        if variant and variant.lower() != 'default title':
            name = f"{name} ({variant})"
        qty = item.get('quantity', 1)
        if qty > 1:
            name = f"{name} x{qty}"
        parts.append(name)
    result = ', '.join(parts)
    extra = len(line_items) - max_items
    if extra > 0:
        result += f' & {extra} more'
    return result


# ── Engine internals ──────────────────────────────────────────────────────────

def _engine_loop():
    while True:
        try:
            _process_due_participants()
        except Exception as e:
            logger.error(f"Flow engine loop error: {e}", exc_info=True)
        time.sleep(15)


def _process_due_participants():
    due = _db.get_due_flow_participants()
    if due:
        logger.debug(f"Flow engine: processing {len(due)} participant(s)")
    for p in due:
        try:
            _process_participant(p)
        except Exception as e:
            logger.error(f"Flow engine: error processing participant {p['id']}: {e}", exc_info=True)
            _db.set_participant_error(p['id'])


def _process_participant(participant):
    # A participant can become "due" and be picked up by two different callers
    # at once: the 15s engine tick (_process_due_participants) and an
    # off-cycle immediate dispatch (enroll_participant's fire-now thread, or
    # trigger_immediate_recheck's fast path making a condition step due right
    # away). Neither path previously marked the row as claimed before doing
    # the work, so if the immediate thread was still blocked on the WhatsApp
    # API call when the next tick fired, both would see the same due
    # send_message step and both would send it -- double-messaging the
    # customer. Claim atomically first; if we lose the race, skip rather than
    # risk executing the step twice.
    if not _db.claim_flow_participant(participant['id']):
        return
    try:
        _process_participant_claimed(participant)
    finally:
        # No-ops if a terminal transition (complete/exit/error) already moved
        # the row out of 'processing'. Otherwise (an early return -- e.g. an
        # off-cycle caller landing on a wait step that isn't due yet, per the
        # comment below -- a condition step's "not yet determinable" retry
        # path, or an unhandled exception) this returns the participant to
        # 'active' so it isn't stuck forever and gets picked up again.
        _db.release_flow_participant(participant['id'])


def _process_participant_claimed(participant):
    flow = _db.get_flow(participant['flow_id'])
    if not flow or flow['status'] != 'active':
        _db.exit_participant(participant['id'], reason='flow_inactive')
        return

    step = _db.get_flow_step(participant['flow_id'], participant['current_step_key'])
    if not step:
        _db.complete_participant(participant['id'])
        return

    step_type = step['step_type']
    try:
        config = json.loads(step['config'] or '{}')
    except Exception:
        config = {}

    if step_type == 'send_message':
        _execute_send_message(participant, step, config)
    elif step_type == 'wait':
        # _process_participant() can run off the normal due-time cycle -- via
        # enroll_participant()'s "fire immediately" thread when a flow's first
        # content step is itself a wait, or via trigger_immediate_recheck().
        # get_due_flow_participants() (the 15s poll) already filters by
        # next_action_at, but those off-cycle callers don't, so re-check here:
        # otherwise landing on a wait step off-cycle advances past it with zero
        # delay, no matter how far in the future next_action_at is.
        if participant.get('next_action_at') and participant['next_action_at'] > _now():
            return
        _advance_to_step(participant, step['next_yes'])
    elif step_type == 'condition':
        _execute_condition(participant, step, config)
    elif step_type == 'generate_discount':
        _execute_generate_discount(participant, step, config)
    elif step_type == 'exit':
        _db.complete_participant(participant['id'])
    elif step_type == 'trigger':
        _advance_to_step(participant, step['next_yes'])


def _resolve_header_media_id(participant, config, context):
    """Resolve the WhatsApp media_id for an image/video/document-header
    template, or None. header_media_type ('image'/'video'/'document') and
    header_media_source ('auto'/'static') are set on the node by the editor
    from template_info()'s detection.

    Only IMAGE has a real 'auto' data source — the participant's order context
    (line_items), fetched via the same Shopify-Admin-API-backed helper the
    legacy order_confirmation automation already uses. VIDEO/DOCUMENT headers
    always use a static, node-configured URL: there's no equivalent 'product
    video'/'product document' concept anywhere else in this codebase to
    auto-fetch from, so offering a dead-end 'auto' option for those would just
    be confusing UI. Either path re-uploads to WhatsApp fresh on every send
    rather than caching a media_id — WhatsApp media IDs expire.

    Non-fatal by design, matching _upload_media_from_url's own convention: if no
    media can be resolved (no header_media_type on this template — including a
    LOCATION header, which Flows doesn't support sending yet — 'auto' with no
    line_items in context, or a download/upload failure), this returns None and
    the send proceeds without a header component. WhatsApp itself will reject a
    send that omits a header a template structurally requires; that failure is
    caught by the existing 'status_code not in (200, 201)' handling below, same
    as any other send failure. Failing the step outright instead of attempting
    the send would need a new error path for the same ultimate outcome
    (participant doesn't get this message) with no extra information for the
    flow owner.
    """
    media_type = config.get('header_media_type')
    if not media_type:
        return None

    from app import _get_product_image_url, _upload_media_from_url

    source = config.get('header_media_source') or ('auto' if media_type == 'image' else 'static')

    if source == 'auto':
        if media_type != 'image':
            return None
        line_items = context.get('line_items') or []
        media_url = _get_product_image_url(line_items)
        if not media_url:
            logger.info(
                f"Flow participant {participant['id']}: 'auto' header media has no "
                f"line_items in context (trigger has no order data) — sending without header"
            )
            return None
        return _upload_media_from_url(media_url, media_type)

    if source == 'upload':
        # A flow stays active enrolling participants for months, but a WhatsApp
        # media_id expires long before that -- so a fixed "upload once" image
        # isn't uploaded to WhatsApp once, it's stored as raw bytes (see
        # utils/database.py's flow_header_images) and re-uploaded fresh here on
        # every send, same non-caching approach as the 'auto'/'static' URL paths.
        ref_id = config.get('header_media_ref_id')
        if not ref_id:
            return None
        image_row = _db.get_flow_header_image(ref_id)
        if not image_row:
            logger.warning(
                f"Flow participant {participant['id']}: uploaded header image "
                f"(ref {ref_id}) not found — sending without header"
            )
            return None
        from utils.whatsapp import upload_media_from_bytes
        return upload_media_from_bytes(
            image_row['image_bytes'], image_row['content_type'], image_row['filename'] or 'header.jpg'
        )

    return _upload_media_from_url(config.get('header_media_url'), media_type)


def _resolve_button_param(entry, context):
    """A button_params entry is either a plain string (the original format --
    always a context key to look up) or the newer {'source':'context','key':..}
    / {'source':'static','value':..} shape, which lets a button (currently only
    COPY_CODE, from the flow editor) carry a fixed value instead of always
    being mapped from participant context. Returns (resolved_value, ctx_key)
    -- ctx_key is None for a static value, so callers can tell "this is a
    context mapping that happened to resolve blank" apart from "this is just
    a literal the flow owner typed".
    """
    if isinstance(entry, dict):
        if entry.get('source') == 'static':
            return entry.get('value', ''), None
        ctx_key = entry.get('key', '')
        return context.get(ctx_key, ''), ctx_key
    # Legacy flat-string format: the entry itself is the context key.
    return context.get(entry, ''), entry


def _execute_send_message(participant, step, config):
    from utils.whatsapp import send_template

    try:
        context = json.loads(participant['context'] or '{}')
    except Exception:
        context = {}

    param_map = config.get('param_map', {})
    if param_map:
        max_pos = max(int(k) for k in param_map.keys())
        params = [context.get(param_map.get(str(i + 1), ''), '') for i in range(max_pos)]
    else:
        params = []

    button_params = {}
    for btn_key, entry in config.get('button_params', {}).items():
        button_params[btn_key], _ = _resolve_button_param(entry, context)

    header_param = None
    header_ctx_key = config.get('header_param')
    if header_ctx_key:
        header_param = context.get(header_ctx_key, '')

    header_media_id = _resolve_header_media_id(participant, config, context)

    template_name = config.get('template_name', '')
    lang = config.get('template_language', 'en_US')

    if not template_name:
        logger.warning(f"Flow participant {participant['id']}: send_message step missing template_name")
        _advance_to_step(participant, step['next_yes'])
        return

    # A mapped context key can still resolve blank -- either the key doesn't
    # apply to this flow's trigger type (e.g. tracking_number mapped on a
    # non-fulfillment flow) or the Shopify payload legitimately omitted it this
    # time (e.g. no courier assigned yet). WhatsApp generally rejects blank body
    # params outright, so surface *why* before the send is attempted rather than
    # letting it fail with only a generic status-code warning.
    blank_mappings = []
    for i in range(len(params)):
        ctx_key = param_map.get(str(i + 1), '')
        if ctx_key and not context.get(ctx_key):
            blank_mappings.append(f"body {{{{{i + 1}}}}}->'{ctx_key}'")
    for btn_key, entry in config.get('button_params', {}).items():
        value, ctx_key = _resolve_button_param(entry, context)
        if ctx_key and not value:
            blank_mappings.append(f"button '{btn_key}'->'{ctx_key}'")
    if header_ctx_key and not context.get(header_ctx_key):
        blank_mappings.append(f"header->'{header_ctx_key}'")
    if blank_mappings:
        logger.warning(
            f"Flow participant {participant['id']}: sending template '{template_name}' with "
            f"blank mapped param(s) (context key resolved empty/missing for this trigger type "
            f"or this webhook payload): {', '.join(blank_mappings)}"
        )

    status_code, response = send_template(
        participant['phone'],
        template_name,
        params,
        lang=lang,
        header_param=header_param,
        header_media_id=header_media_id,
        header_media_type=config.get('header_media_type') or 'image',
        button_params=button_params or None
    )

    wamid = None
    if isinstance(response, dict):
        msgs = response.get('messages', [])
        wamid = msgs[0].get('id') if msgs else None

    _db.add_flow_message(
        flow_id=participant['flow_id'],
        participant_id=participant['id'],
        step_key=step['step_key'],
        phone=participant['phone'],
        wamid=wamid
    )

    if status_code not in (200, 201):
        logger.warning(
            f"Flow participant {participant['id']}: send failed ({status_code}), advancing anyway"
        )

    _advance_to_step(participant, step['next_yes'])


def _execute_condition(participant, step, config):
    condition_type = config.get('condition_type', '')
    hours = int(config.get('hours', 24))

    last_msg = _db.get_last_flow_message(participant['id'])
    result = None  # True / False / None (not yet determinable)

    if condition_type == 'replied_within_X_hours':
        if last_msg:
            if last_msg.get('replied_at'):
                sent = _parse_dt(last_msg['sent_at'])
                replied = _parse_dt(last_msg['replied_at'])
                result = (replied - sent).total_seconds() <= hours * 3600
            elif last_msg.get('sent_at'):
                sent = _parse_dt(last_msg['sent_at'])
                if datetime.now(timezone.utc).replace(tzinfo=None) > sent + timedelta(hours=hours):
                    result = False
        else:
            result = False

    elif condition_type == 'read_within_X_hours':
        if last_msg:
            if last_msg.get('read_at'):
                sent = _parse_dt(last_msg['sent_at'])
                read = _parse_dt(last_msg['read_at'])
                result = (read - sent).total_seconds() <= hours * 3600
            elif last_msg.get('sent_at'):
                sent = _parse_dt(last_msg['sent_at'])
                if datetime.now(timezone.utc).replace(tzinfo=None) > sent + timedelta(hours=hours):
                    result = False
        else:
            result = False

    elif condition_type == 'placed_order':
        result = _db.customer_placed_order_since(participant['phone'], participant['enrolled_at'])

    elif condition_type == 'order_fulfilled':
        # Point-in-time check, same as placed_order -- no hours window. Abhi's
        # use case (Order Placed -> Wait 4 days -> if NOT dispatched, remind)
        # already does its waiting in the Wait step; this just asks "is it
        # fulfilled right now?" once the flow reaches this step.
        try:
            context = json.loads(participant['context'] or '{}')
        except Exception:
            context = {}
        shopify_order_id = context.get('shopify_order_id')
        if shopify_order_id:
            order = _db.get_order_by_shopify_id(shopify_order_id)
            if order:
                result = (order.get('fulfillment_status') == 'fulfilled')
            # else: order row doesn't exist yet (webhook ordering/timing) --
            # leave result None so the generic retry-in-15-min path below
            # gives it a chance to show up, rather than assuming False forever.
        # else: this flow's trigger type never populated shopify_order_id (not
        # an order-bearing trigger) -- also leave as not-yet-determinable
        # rather than crash; the flow owner shouldn't have used this condition
        # here, but nothing about this state resolves it either way.

    elif condition_type == 'cancel_reason_is':
        # Unlike placed_order/order_fulfilled, this never needs the
        # retry-in-15-min path -- cancel_reason is already in participant
        # context from enrollment (build_trigger_context() reads it straight
        # off the orders/cancelled webhook payload, no later async event to
        # wait for), so it's always immediately determinable one way or the
        # other. A flow using this condition on a non-order_cancelled trigger
        # (context never populated it) resolves False, same fail-safe
        # rather than crash as order_fulfilled's missing-shopify_order_id case.
        expected_reason = config.get('reason', '')
        if expected_reason:
            try:
                context = json.loads(participant['context'] or '{}')
            except Exception:
                context = {}
            result = (context.get('cancel_reason', '') == expected_reason)
        else:
            # Unconfigured (flow owner never picked a reason) -- resolve False
            # rather than let two blank strings coincidentally "match".
            result = False

    if result is True:
        _advance_to_step(participant, step['next_yes'])
    elif result is False:
        _advance_to_step(participant, step['next_no'])
    else:
        _db.update_participant_next_action(
            participant['id'],
            (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%S')
        )


def _execute_generate_discount(participant, step, config):
    """Generates a unique one-time-use Shopify discount code and stores it on
    the participant's context (key 'discount_code') for a later send_message
    step to map into a template variable. Unlike order-derived context keys
    (order_number, items, ...), this isn't tied to any particular trigger
    type -- the code is created fresh right here, so it works the same way
    regardless of what started the flow.
    """
    try:
        context = json.loads(participant['context'] or '{}')
    except Exception:
        context = {}

    percentage = int(config.get('percentage') or 10)
    never_expire = config.get('never_expire', True)
    expiry_date = config.get('expiry_date') or ''

    ends_at = None
    if not never_expire and expiry_date:
        # expiry_date is a plain YYYY-MM-DD from the editor's <input type=date>;
        # treat it as end-of-day UTC so the code stays valid through the whole
        # day the flow owner picked, matching create_price_rule_with_discount_code's
        # own starts_at convention (a UTC ISO 8601 timestamp).
        ends_at = f"{expiry_date}T23:59:59+00:00"

    first_name = (context.get('first_name') or '').strip()
    if not first_name:
        # Manual enrollment (and any trigger type that never populates
        # first_name) doesn't have it in context -- look the customer up by
        # phone the same way the legacy abandoned-cart checker does, before
        # falling back to a generic placeholder rather than crashing or
        # producing a malformed code.
        try:
            customer = _db.get_customer_by_phone(participant['phone'])
            if customer and customer.get('first_name'):
                first_name = customer['first_name'].strip()
        except Exception:
            pass
    if not first_name:
        first_name = 'CUSTOMER'

    discount_code = _generate_flow_discount_code(percentage, first_name)

    from app import _create_discount_code_in_shopify
    price_rule_id, created_code = _create_discount_code_in_shopify(
        discount_code, percentage=percentage, ends_at=ends_at
    )

    if created_code:
        context['discount_code'] = created_code
        _db.update_participant_context(participant['id'], context)
        logger.info(f"Flow participant {participant['id']}: generated discount code {created_code}")
    else:
        # Non-fatal by design, matching every other Shopify-write-failure path
        # in this codebase -- the flow keeps moving. 'discount_code' is simply
        # left unset in context, so a downstream send_message step mapping it
        # hits the existing blank-mapped-param warning at send time rather
        # than silently sending a broken/missing code.
        logger.warning(
            f"Flow participant {participant['id']}: discount code creation failed in Shopify -- "
            f"'discount_code' left unset in context"
        )

    _advance_to_step(participant, step['next_yes'])


def _generate_flow_discount_code(percentage, first_name):
    """SAVE<percentage>-<sanitized first name>-<random suffix>, e.g.
    'SAVE20-JOHN-K3F9QZ'. The random suffix guards against two customers
    sharing a first name colliding on the same code -- Shopify discount codes
    must be unique across the whole store."""
    name_part = re.sub(r'[^A-Za-z0-9]', '', first_name).upper()[:15] or 'CUSTOMER'
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"SAVE{percentage}-{name_part}-{suffix}"


def _next_action_at_for_entering(step):
    """Due time for a participant that is about to be *entered onto* `step`
    (whether via enrollment or by advancing from a prior step). A 'wait' step
    needs its hours-delay computed now, at entry time -- not at the point it's
    later found due, by which time the delay has already elapsed. Uses the
    same no-microseconds format as _now() so every next_action_at value in the
    DB compares consistently against SQLite's strftime('%Y-%m-%dT%H:%M:%S',
    'now') in get_due_flow_participants(), regardless of which code path wrote
    it (isoformat() includes microseconds and, unlike _now(), was previously
    used here).
    """
    if step and step['step_type'] == 'wait':
        try:
            config = json.loads(step['config'] or '{}')
        except Exception:
            config = {}
        hours = int(config.get('hours', 1))
        return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S')
    return _now()


def _advance_to_step(participant, next_step_key):
    if not next_step_key:
        _db.complete_participant(participant['id'])
        return

    next_step = _db.get_flow_step(participant['flow_id'], next_step_key)
    if not next_step:
        _db.complete_participant(participant['id'])
        return

    next_action_at = _next_action_at_for_entering(next_step)
    _db.update_participant_step(participant['id'], next_step_key, next_action_at)


def _parse_dt(s):
    if not s:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc).replace(tzinfo=None)
