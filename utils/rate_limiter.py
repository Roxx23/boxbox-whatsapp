import time
import threading
from queue import Queue, Empty
from collections import deque
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Thread-safe rate limiter for WhatsApp Cloud API
    
    WhatsApp Cloud API Limits:
    - 80 messages per second (Business API)
    - 1000 messages per second (Cloud API with approved limits)
    - Recommended: 20-50 messages per second for safety
    """
    
    def __init__(self, max_requests=20, time_window=1.0):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in time_window
            time_window: Time window in seconds (default 1 second)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Block if rate limit is reached"""
        with self.lock:
            now = time.time()
            
            # Remove old requests outside time window
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()
            
            # If at limit, wait until oldest request expires
            if len(self.requests) >= self.max_requests:
                sleep_time = self.requests[0] + self.time_window - now
                if sleep_time > 0:
                    logger.info(f"⏳ Rate limit reached. Waiting {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                    # Clean up again after waiting
                    self.requests.popleft()
            
            # Record this request
            self.requests.append(time.time())


class MessageQueue:
    """
    Thread-safe message queue with worker threads
    Handles retries and error recovery
    """
    
    def __init__(self, rate_limiter, num_workers=1):
        """
        Initialize message queue
        
        Args:
            rate_limiter: RateLimiter instance
            num_workers: Number of worker threads (default 1 for sequential sending)
        """
        self.queue = Queue()
        self.rate_limiter = rate_limiter
        self.num_workers = num_workers
        self.workers = []
        self.running = False
        self.results = []
        self.results_lock = threading.Lock()
    
    def ensure_workers_running(self):
        """Detect and restart any dead worker threads."""
        if not self.running:
            return
        dead = [w for w in self.workers if not w.is_alive()]
        for w in dead:
            logger.warning("⚠️ Worker thread found dead — restarting")
            self.workers.remove(w)
            new_worker = threading.Thread(target=self._worker, daemon=True)
            new_worker.start()
            self.workers.append(new_worker)

    def add_message(self, send_function, *args, user_id=None, username=None, campaign_id=None, message_id=None, **kwargs):
        """
        Add a message to the queue
        
        Args:
            send_function: The function to call (e.g., send_template, send_text)
            *args, **kwargs: Arguments to pass to send_function
            user_id: ID of user sending the message
            username: Username of user sending the message
            campaign_id: ID of the campaign (optional)
            message_id: ID of the message record in database (optional)
        """
        self.ensure_workers_running()
        self.queue.put({
            'function': send_function,
            'args': args,
            'kwargs': kwargs,
            'retries': 0,
            'max_retries': 3,
            'user_id': user_id,
            'username': username or 'System',
            'campaign_id': campaign_id,
            'message_id': message_id
        })
    
    def _worker(self):
        """Worker thread that processes messages from queue"""
        logger.info("Worker thread started")
        while self.running:
            try:
                # Get message with timeout to allow checking running flag
                message = self.queue.get(timeout=1)

                # Rate limit before sending
                try:
                    self.rate_limiter.wait_if_needed()
                except Exception as e:
                    logger.error(f"❌ Rate limiter error: {e}")

                # Send the message
                try:
                    status, response = message['function'](
                        *message['args'],
                        **message['kwargs']
                    )

                    # Handle rate limit response (429)
                    if status == 429:
                        if message['retries'] < message['max_retries']:
                            message['retries'] += 1
                            wait_time = 2 ** message['retries']  # Exponential backoff
                            logger.warning(f"⚠️ Rate limited (429). Retry {message['retries']}/{message['max_retries']} in {wait_time}s")
                            time.sleep(wait_time)
                            self.queue.put(message)  # Re-queue
                        else:
                            logger.error(f"❌ Max retries reached for message")
                            self._record_result(message, status, response, failed=True)

                    # Handle other errors
                    elif status >= 400:
                        logger.error(f"❌ API error {status} sending to {message['args'][0] if message['args'] else '?'}: {response}")
                        if message['retries'] < message['max_retries']:
                            message['retries'] += 1
                            logger.warning(f"⚠️ Retry {message['retries']}/{message['max_retries']}")
                            self.queue.put(message)  # Re-queue immediately (no sleep)
                        else:
                            logger.error(f"❌ Failed after {message['max_retries']} retries: {response}")
                            self._record_result(message, status, response, failed=True)

                    # Success
                    else:
                        logger.info(f"✅ Message sent successfully")
                        self._record_result(message, status, response, failed=False)

                except Exception as e:
                    logger.error(f"❌ Exception sending message: {e}")
                    self._record_result(message, 500, str(e), failed=True)

                finally:
                    self.queue.task_done()

            except Empty:
                continue  # No message available, continue loop
            except Exception as e:
                # Catch-all: log but keep the worker alive
                logger.error(f"❌ CRITICAL worker error (thread stays alive): {e}", exc_info=True)
                continue
    
    def _record_result(self, message, status, response, failed):
        """Thread-safe result recording with database logging"""
        with self.results_lock:
            self.results.append({
                'status': status,
                'response': response,
                'failed': failed,
                'retries': message['retries'],
                'timestamp': datetime.now()
            })
            
            # Log to database
            try:
                from utils.database import Database
                
                db = Database()
                
                user_id = message.get('user_id')
                username = message.get('username', 'System')
                campaign_id = message.get('campaign_id')
                
                # Extract phone number and message type
                phone = 'Unknown'
                action = 'Message Sent'
                details = ''
                
                if len(message['args']) > 0:
                    phone = str(message['args'][0])
                
                if message['function'].__name__ == 'send_template':
                    template_name = message['args'][1] if len(message['args']) > 1 else 'Unknown'
                    action = 'Template Message'
                    details = f"Template: {template_name}, To: {phone}, Status: {'Success' if not failed else 'Failed'}"
                elif message['function'].__name__ == 'send_text':
                    action = 'Text Message'
                    details = f"To: {phone}, Status: {'Success' if not failed else 'Failed'}"
                
                # Log activity
                if user_id:
                    db.log_activity(
                        user_id=user_id,
                        username=username,
                        action=action,
                        details=details,
                        ip_address='127.0.0.1'
                    )
                    
                    # Track template usage
                    if message['function'].__name__ == 'send_template' and not failed:
                        template_name = message['args'][1] if len(message['args']) > 1 else None
                        if template_name:
                            db.track_template_usage(user_id, username, template_name)
                
                # Extract WhatsApp message ID from response
                whatsapp_message_id = None
                if not failed and response and isinstance(response, dict):
                    # WhatsApp API returns message ID in different structures
                    if 'messages' in response and len(response['messages']) > 0:
                        whatsapp_message_id = response['messages'][0].get('id')
                    elif 'id' in response:
                        whatsapp_message_id = response.get('id')
                
                # Update message record in database
                message_id = message.get('message_id')
                if message_id:
                    message_status = 'failed' if failed else 'sent'
                    error_msg = str(response) if failed else None
                    db.update_message_status(
                        message_id,
                        status=message_status,
                        error_message=error_msg,
                        whatsapp_message_id=whatsapp_message_id
                    )
                    logger.info(f"✅ Updated message #{message_id} with WhatsApp ID: {whatsapp_message_id}")

                
                # Update campaign counts
                if campaign_id:
                    campaign = db.get_campaign(campaign_id)
                    if campaign:
                        new_success = campaign.get('success_count', 0)
                        new_failed = campaign.get('failed_count', 0)
                        
                        if failed:
                            new_failed += 1
                        else:
                            new_success += 1
                        
                        # Update campaign status to running if it was pending
                        campaign_status = campaign.get('status', 'pending')
                        if campaign_status == 'pending':
                            campaign_status = 'running'
                        
                        # Check if campaign is complete
                        total_sent = new_success + new_failed
                        recipient_count = campaign.get('recipient_count', 0)
                        
                        if total_sent >= recipient_count and recipient_count > 0:
                            campaign_status = 'completed'
                            db.update_campaign_status(
                                campaign_id=campaign_id,
                                status=campaign_status,
                                success_count=new_success,
                                failed_count=new_failed,
                                completed_at=datetime.now().isoformat()
                            )
                        else:
                            db.update_campaign_status(
                                campaign_id=campaign_id,
                                status=campaign_status,
                                success_count=new_success,
                                failed_count=new_failed
                            )
            except Exception as e:
                logger.error(f"Failed to log message to database: {e}")
    
    def start(self):
        """Start worker threads"""
        self.running = True
        for i in range(self.num_workers):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            self.workers.append(worker)
        logger.info(f"🚀 Started {self.num_workers} worker thread(s)")
    
    def stop(self):
        """Stop worker threads gracefully"""
        logger.info("⏹️ Stopping workers...")
        self.running = False
        for worker in self.workers:
            worker.join(timeout=5)
        logger.info("✅ All workers stopped")
    
    def wait_completion(self, timeout=None):
        """Wait for all messages to be processed"""
        self.queue.join()
        logger.info("✅ All messages processed")
    
    def get_results(self):
        """Get all results thread-safely"""
        with self.results_lock:
            return self.results.copy()
    
    def get_stats(self):
        """Get processing statistics"""
        with self.results_lock:
            total = len(self.results)
            successful = sum(1 for r in self.results if not r['failed'])
            failed = sum(1 for r in self.results if r['failed'])
            alive_workers = sum(1 for w in self.workers if w.is_alive())

            return {
                'total': total,
                'successful': successful,
                'failed': failed,
                'success_rate': (successful / total * 100) if total > 0 else 0,
                'pending': self.queue.qsize(),
                'workers_alive': alive_workers,
                'workers_total': len(self.workers)
            }


# ==============================================================
# USAGE EXAMPLE
# ==============================================================

if __name__ == "__main__":
    from utils.whatsapp import send_text, send_template
    
    # Initialize rate limiter (20 messages per second)
    rate_limiter = RateLimiter(max_requests=20, time_window=1.0)
    
    # Initialize message queue with 1 worker
    message_queue = MessageQueue(rate_limiter, num_workers=1)
    
    # Start processing
    message_queue.start()
    
    # Add messages to queue
    recipients = [
        {"phone": "+919156143465", "name": "Alice"},
        {"phone": "+919876543210", "name": "Bob"},
        # ... more recipients
    ]
    
    for recipient in recipients:
        # Add text message
        message_queue.add_message(
            send_text,
            recipient['phone'],
            f"Hello {recipient['name']}!"
        )
        
        # OR add template message
        # message_queue.add_message(
        #     send_template,
        #     recipient['phone'],
        #     'your_template_name',
        #     ['param1', 'param2'],
        #     'en_US'
        # )
    
    # Wait for all messages to complete
    message_queue.wait_completion()
    
    # Get statistics
    stats = message_queue.get_stats()
    print(f"\n📊 Statistics:")
    print(f"Total: {stats['total']}")
    print(f"Successful: {stats['successful']}")
    print(f"Failed: {stats['failed']}")
    print(f"Success Rate: {stats['success_rate']:.1f}%")
    
    # Stop workers
    message_queue.stop()