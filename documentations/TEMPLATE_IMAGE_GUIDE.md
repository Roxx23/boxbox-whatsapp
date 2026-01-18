# WhatsApp Template Image Upload Guide

## ⚠️ IMPORTANT: Template Creation Requires URLs Only

**WhatsApp template creation ONLY accepts publicly accessible image URLs.**

File uploads will NOT work for template creation because:
- WhatsApp media upload returns a media ID (not a URL)
- Template creation API requires a real HTTPS URL for approval
- The image must be accessible to WhatsApp's review team

**Bottom line: You MUST use an image URL (Option 1 below). File upload is not available for template creation.**

---

## Option 1: Image URL (REQUIRED) ✅
Provide a **publicly accessible HTTPS URL** to your image.

### Requirements:
- Must be a valid HTTPS URL (starts with `https://`)
- Image must be publicly accessible (no authentication required)
- Supported formats: JPG, PNG, GIF, WebP
- Maximum file size: 5MB
- Recommended dimensions: 800x418 pixels (for optimal display)

### Example URLs:
```
https://i.imgur.com/abc123.jpg (Imgur - direct link)
https://example.com/images/header-image.jpg
https://cdn.yoursite.com/templates/promo.png
```

### ⚠️ Common Mistakes:
**Wrong (Imgur album/gallery page):**
```
https://imgur.com/a/1qAj0An  ❌ (This is a page, not an image)
https://imgur.com/gallery/xxxxx  ❌ (This is a gallery page)
```

**Correct (Direct image link):**
```
https://i.imgur.com/1qAj0An.jpg  ✅ (Direct image URL)
https://i.imgur.com/1qAj0An.png  ✅ (Direct image URL)
```

### How to get direct image link from Imgur:
1. Open your image on Imgur
2. **Right-click** on the image itself
3. Select **"Copy image address"** or **"Copy image URL"**
4. The URL should start with `https://i.imgur.com/` and end with `.jpg` or `.png`
5. Alternatively, add `.jpg` or `.png` extension to your Imgur link

---

## ~~Option 2: File Upload~~ (NOT AVAILABLE FOR TEMPLATES)

**File upload is NOT supported for template creation.** This is a WhatsApp API limitation.

### Why doesn't file upload work?
- WhatsApp's media upload API returns a media ID (e.g., "123456789")
- The template creation API requires a publicly accessible URL
- Media IDs work for sending messages, but NOT for creating templates

### What to do instead:
Upload your image to a free hosting service and use the URL (see Option 1 above).
1. **Free image hosting services:**
   - [ImgBB](https://imgbb.com/)
   - [Imgur](https://imgur.com/)
   - [Cloudinary](https://cloudinary.com/) (free tier)

2. **Your own web server:**
   - Upload to your website's public directory
   - Ensure the image is accessible via HTTPS
   - Test the URL in a browser before using it

3. **Cloud storage:**
   - AWS S3 with public read access
   - Google Cloud Storage with public link
   - Azure Blob Storage with public access

## Option 2: File Upload
Upload an image file directly through the form.

### How it works:
1. Click the upload area or browse for a file
2. Select an image (JPG, PNG, GIF, or WebP)
3. File is uploaded to WhatsApp's media API
4. Media ID is used for template creation

### Limitations:
- File size: Maximum 5MB
- Upload depends on WhatsApp API availability
- May have network-related issues
- Less reliable than using a URL

### File size validation:
- Client-side: Validates before upload
- Server-side: Double-checks size and format
- Error messages guide you if file is too large or wrong format

## Best Practices

### ✅ DO:
- Use HTTPS URLs (required by WhatsApp)
- Test your image URL in a browser first
- Use standard image formats (JPG, PNG)
- Keep file sizes under 2MB for faster loading
- Use appropriate dimensions (800x418px recommended)

### ❌ DON'T:
- Use HTTP URLs (will be rejected)
- Use password-protected or private URLs
- Use very large files (>5MB)
- Use animated GIFs for professional templates
- Forget to test the URL before submitting

## Troubleshooting

### "Failed to upload image"
- **Try using an HTTPS URL instead** - This is more reliable
- Check your internet connection
- Ensure file size is under 5MB
- Verify file format is supported

### "Image URL must start with https://"
- WhatsApp requires secure HTTPS URLs
- Change `http://` to `https://` in your URL
- Use a hosting service that supports HTTPS

### "Please provide either an image file or image URL"
- You must select either:
  - Enter an image URL in the URL field, OR
  - Upload a file using the file picker
- At least one option is required for IMAGE header type

## Example Workflow

### Using URL (Recommended):
1. Upload your image to ImgBB or similar service
2. Copy the direct HTTPS link
3. Paste it in the "Image URL" field
4. Leave the file upload empty
5. Submit the template

### Using File Upload:
1. Leave the "Image URL" field empty
2. Click the upload area
3. Select your image file (under 5MB)
4. Wait for preview to appear
5. Submit the template

## API Details

### WhatsApp Template API Requirements:
- Templates with IMAGE headers need an `example.header_handle` array
- The handle must be a publicly accessible URL or valid media ID
- Images are used as examples for template approval
- Actual message sending can use different images

### Media Upload API:
- Endpoint: `https://graph.facebook.com/v20.0/{phone-number-id}/media`
- Returns a media ID that can be used as a handle
- Uploaded media is stored temporarily on WhatsApp servers

## Need Help?

If you continue to experience issues:
1. Check console logs for detailed error messages
2. Verify your WhatsApp Business API credentials
3. Ensure your WABA has permissions to create templates
4. Try the URL method if file upload fails
5. Contact WhatsApp Business API support if issues persist
