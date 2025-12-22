from flask import Flask, render_template, request, flash, redirect, jsonify
import pandas as pd
import time

from utils.personalize import personalize
from utils.whatsapp import send_text, get_templates, send_template, upload_media
from utils.logger import log_message
from utils.background_scheduler import schedule_message_job, get_scheduled_jobs, cancel_job

WABA_ID = "2252354741929132"

app = Flask(__name__)
app.secret_key = "change-this-key"

# Add this route for template creation page
@app.route("/create-template", methods=["GET"])
def create_template_page():
    return render_template("create_template.html")


# Add this route to handle template submission
@app.route("/submit-template", methods=["POST"])
def submit_template():
    try:
        template_data = {
            'template_name': request.form.get('template_name'),
            'category': request.form.get('category'),
            'language': request.form.get('language'),
            'header_type': request.form.get('header_type'),
            'header_text': request.form.get('header_text'),
            'header_image_url': request.form.get('header_image_url'),  # Add this line
            'body_text': request.form.get('body_text'),
            'footer_text': request.form.get('footer_text'),
        }
        
        # Get button data
        for i in range(1, 4):
            template_data[f'button_type_{i}'] = request.form.get(f'button_type_{i}')
            template_data[f'button_text_{i}'] = request.form.get(f'button_text_{i}')
            template_data[f'button_value_{i}'] = request.form.get(f'button_value_{i}')
        
        # Import the function
        from utils.whatsapp import create_template
        
        status, response = create_template(WABA_ID, template_data, None)
        
        if status in [200, 201]:
            flash(f"✅ Template '{template_data['template_name']}' submitted successfully! It will be reviewed by WhatsApp.")
        else:
            error_msg = "Unknown error"
            if 'error' in response:
                if isinstance(response['error'], dict):
                    error_msg = response['error'].get('message', str(response['error']))
                else:
                    error_msg = str(response['error'])
            
            flash(f"❌ Error: {error_msg}")
            print(f"Full error response: {response}")
        
        return redirect("/create-template")
    
    except Exception as e:
        import traceback
        print(f"Exception traceback: {traceback.format_exc()}")
        flash(f"❌ Error creating template: {str(e)}")
        return redirect("/create-template")

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


# New route to view scheduled jobs
@app.route("/scheduled-jobs")
def scheduled_jobs():
    jobs = get_scheduled_jobs()
    return jsonify({"jobs": jobs})


# New route to cancel a job
@app.route("/cancel-job/<job_id>", methods=["POST"])
def cancel_scheduled_job(job_id):
    success, message = cancel_job(job_id)
    return jsonify({"success": success, "message": message})


@app.route("/", methods=["GET", "POST"])
def index():
    results = []
    templates = get_templates(WABA_ID)

    template_param_count = 0
    csv_columns = []

    if request.method == "POST":
        csv_file = request.files.get("csv_file")
        template_name = request.form.get("template_name")
        message_template = request.form.get("message_template")
        send_mode = request.form.get("send_mode")
        send_time = request.form.get("send_time")

        if not csv_file:
            flash("Please upload CSV.")
            return redirect("/")

        df = pd.read_csv(csv_file)
        csv_columns = list(df.columns)

        if "Phone" not in csv_columns:
            flash("CSV must contain a 'Phone' column.")
            return redirect("/")

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
        # Detect if template requires IMAGE header
        # ----------------------------
        header_needs_image = False
        header_component = None

        if selected_template:
            header_component = next(
                (c for c in selected_template["components"] if c["type"] == "HEADER"),
                None
            )
            if header_component and header_component.get("format") == "IMAGE":
                header_needs_image = True
        
        # ----------------------------
        # Upload IMAGE HEADER ONCE (VERY IMPORTANT)
        # ----------------------------
        header_media_id = None
        
        if selected_template and header_needs_image:
            image_file = request.files.get("header_image")
        
            if not image_file or image_file.filename == "":
                flash("This template requires an IMAGE header. Please upload a header image.")
                return redirect("/")
        
            header_media_id = upload_media(image_file)
        
            if not header_media_id:
                flash("Header image upload failed. Please try again.")
                return redirect("/")
        


        # ==============================================================
        # SCHEDULED SENDING
        # ==============================================================
        if send_mode == "later":
            if not send_time:
                flash("Please enter a scheduled time.")
                return redirect("/")
            
            # Prepare parameters for scheduled job
            if selected_template:
                params_mapping = []
                for i in range(template_param_count):
                    col = request.form.get(f"param{i+1}")
                    if not col:
                        flash(f"Please map all template parameters.")
                        return redirect("/")
                    params_mapping.append(col)
                
                success, message = schedule_message_job(
                    df=df,
                    template_name=template_name,
                    template_language=template_language,
                    template_params_mapping=params_mapping,
                    send_time_str=send_time
                )
            else:
                if not message_template:
                    flash("Please enter a message template.")
                    return redirect("/")
                
                success, message = schedule_message_job(
                    df=df,
                    message_template=message_template,
                    send_time_str=send_time
                )
            
            if success:
                flash(f"✅ {message}", "success")
            else:
                flash(f"❌ {message}", "error")
            
            return redirect("/")

        # ==============================================================
        # IMMEDIATE SENDING
        # ==============================================================
        if selected_template:
            if any(request.form.get(f"param{i+1}") is None for i in range(template_param_count)):
                return render_template(
                    "index.html",
                    results=results,
                    templates=templates,
                    template_param_count=template_param_count,
                    csv_columns=csv_columns
                )

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

                status, resp = send_template(
                    phone,
                    template_name,
                    params,
                    template_language,
                    header_media_id=header_media_id
                )


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

        # Free text messages
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

    return render_template(
        "index.html",
        results=results,
        templates=templates,
        template_param_count=template_param_count,
        csv_columns=csv_columns
    )


if __name__ == "__main__":
    app.run(debug=True)