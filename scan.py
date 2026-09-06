import qrcode
from PIL import Image, ImageEnhance

URL = "https://passiflora-pooja-app.streamlit.app/"

# 1. Generate QR code with High Error Correction (H)
# High ECC allows up to 30% of the QR code to be covered/customized without scan failure
qr = qrcode.QRCode(
    version=4,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=10,
    border=4,
)
qr.add_data(URL)
qr.make(fit=True)

# Generate QR image (Deep maroon on transparent/white background)
qr_img = qr.make_image(fill_color="#8B0000", back_color="white").convert("RGBA")

# 2. (Optional) Overlay onto a custom Ganpati Bappa Background Image
# If you have a background file named 'ganpati_bg.jpg':
try:
    bg = Image.open("ganpati_bg.jpg").convert("RGBA")
    
    # Resize QR to fit nicely inside the background canvas
    target_qr_width = int(bg.width * 0.55)
    qr_img = qr_img.resize((target_qr_width, target_qr_width), Image.Resampling.LANCZOS)
    
    # Calculate center position
    pos_x = (bg.width - qr_img.width) // 2
    pos_y = int(bg.height * 0.45)  # slightly lowered to keep face visible
    
    # Paste QR on top of background
    bg.paste(qr_img, (pos_x, pos_y), qr_img)
    bg.convert("RGB").save("pooja_booking_standee.png", quality=95)
    print("✓ Created pooja_booking_standee.png with custom Ganpati background!")

except FileNotFoundError:
    # Standalone QR output if background file isn't present yet
    qr_img.convert("RGB").save("pooja_qr_code.png")
    print("✓ Saved high-contrast scannable QR as pooja_qr_code.png")