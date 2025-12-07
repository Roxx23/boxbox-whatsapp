from flask import Flask, render_template, request, flash, redirect, jsonify
import pandas as pd
import time
from utils.personalize import personalize
from utils.whatsapp import send_text, get_templates, send_template
from utils.logger import log_message
from utils.scheduler import wait_until

WABA_ID = "1049693173949491"

app = Flask(__name__)
app.secret_key = "change-this-key"

@app.route("/get-csv-columns", methods=["POST"])
def get_csv_columns():
    csv_file = request.files.get("csv_file")
    if not csv_file:
        return jsonify({"error": "No file uploaded"}), 400
    
    try:
        df = pd.read_csv(csv_file)
        columns = list(df.columns)
        return jsonify({"columns": columns})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# -------------------------------------------------------------------
# API: Get template parameter count (AJAX, used by frontend JS)
# -------------------------------------------------------------------
@app.route("/template-info")
def template_info():
    template_name = request.args.get("name")
    templates = get_templates(WABA_ID)

    selected = next((t for t in templates if t["name"] == template_name), None)

    count = 0
    if selected:
        body = next((c for c in selected["components"] if c["type"] == "BODY"), None)
        if body and "text" in body:
            count = body["text"].count("{{")

    return jsonify({"count": count})


# -------------------------------------------------------------------
# MAIN DASHBOARD
# -------------------------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    templates = get_templates(WABA_ID)

    template_param_count = 0
    csv_columns = []

    # Only POST triggers sending messages
    if request.method == "POST":

        # ----------------------------
        # Read submitted form values
        # ----------------------------
        csv_file = request.files.get("csv_file")
        template_name = request.form.get("template_name")
        message_template = request.form.get("message_template")
        send_mode = request.form.get("send_mode")
        send_time = request.form.get("send_time")

        # ----------------------------
        # Validate CSV
        # ----------------------------
        if not csv_file:
            flash("Please upload CSV.")
            return redirect("/")

        df = pd.read_csv(csv_file)
        csv_columns = list(df.columns)

        if "Phone" not in csv_columns:
            flash("CSV must contain a 'Phone' column.")
            return redirect("/")

        # ----------------------------
        # Detect template parameter count (if template selected)
        # ----------------------------
        selected_template = next((t for t in templates if t["name"] == template_name), None)
        template_language = "en"

        if selected_template:
            template_language = selected_template.get("language", "en")

            body_component = next(
                (c for c in selected_template["components"] if c["type"] == "BODY"),
                None
            )
            if body_component and "text" in body_component:
                template_param_count = body_component["text"].count("{{")

        # ----------------------------
        # Scheduling
        # ----------------------------
        if send_mode == "later":
            if not send_time:
                flash("Enter a scheduled time.")
                return redirect("/")
            wait_until(send_time)

        # ==============================================================
        # CASE 1 — TEMPLATE MESSAGE FLOW
        # ==============================================================
        if selected_template:

            # Ensure template parameters were mapped
            if any(request.form.get(f"param{i+1}") is None for i in range(template_param_count)):
                return render_template(
                    "index.html",
                    results=results,
                    templates=templates,
                    template_param_count=template_param_count,
                    csv_columns=csv_columns
                )

            # Send template messages
            for idx, row in df.iterrows():
                row_dict = row.to_dict()
                name = row_dict.get("Name", "")
                phone = str(row_dict.get("Phone"))

                params = []
                for i in range(template_param_count):
                    col = request.form.get(f"param{i+1}")
                    val = row_dict.get(col)

                    if val is None:
                        flash(f"Column '{col}' missing in CSV")
                        return redirect("/")

                    params.append(str(val))

                status, resp = send_template(phone, template_name, params, template_language)

                results.append({
                    "name": name,
                    "phone": phone,
                    "message": f"TEMPLATE: {template_name} → {params}",
                    "status": status
                })

                log_message(name, phone, str(params), status, resp)
                time.sleep(1)
            flash(f"Template message '{template_name}' sent to {len(results)} contacts.")

            return render_template(
                "index.html",
                results=results,
                templates=templates,
                template_param_count=template_param_count,
                csv_columns=csv_columns
            )

        # ==============================================================
        # CASE 2 — FREE TEXT MESSAGE FLOW
        # ==============================================================
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            name = row_dict.get("Name", "")
            phone = str(row_dict.get("Phone")).strip()

            personalized_msg = personalize(message_template, row_dict, idx + 1)
            status, resp = send_text(phone, personalized_msg)

            results.append({
                "name": name,
                "phone": phone,
                "message": personalized_msg,
                "status": status
            })

            log_message(name, phone, personalized_msg, status, resp)
            time.sleep(1)
        flash(f"Text message sent to {len(results)} contacts.")

    # ----------------------------------------------------------------
    # GET request simply renders the UI
    # ----------------------------------------------------------------
    return render_template(
        "index.html",
        results=results,
        templates=templates,
        template_param_count=template_param_count,
        csv_columns=csv_columns
    )


# -----------------------------
# START APP
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)
