from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image, ImageDraw, ImageFont
import io
import json
import os

app = FastAPI()

# --- 1. CẤU HÌNH FONT ---
FONT_DIR = "fonts"
# M chỉ cần 2 file này (hoặc 1 file dùng chung cũng được)
PATH_STANDARD = os.path.join(FONT_DIR, "CruyffSansCondensed-Bold.otf")
PATH_NAME = os.path.join(FONT_DIR, "CruyffSansCondensed-Bold.otf")

def load_font(path, size):
    if os.path.exists(path):
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# --- 2. HÀM VẼ TÊN "BÓP DẸT" (SQUASH) ---
def draw_name_squash(overlay_img, text, font_path, color, y_baseline, max_width=156):
    """
    Nếu tên ngắn: Vẽ bình thường.
    Nếu tên dài > max_width: Vẽ ra ảnh tạm -> Bóp chiều ngang -> Dán vào.
    """
    # 1. Load font chuẩn size 24
    font_size = 24
    if os.path.exists(font_path):
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    # Tạo một đối tượng draw tạm để đo kích thước
    temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    # 2. Đo chiều rộng thật của text
    text_w = temp_draw.textlength(text, font=font)

    # Lấy thêm thông tin chiều cao (Ascent/Descent) để căn chỉnh Y cho chuẩn
    ascent, descent = font.getmetrics()
    # Tổng chiều cao của dòng chữ (từ đỉnh cao nhất đến đáy thấp nhất)
    # Tuy nhiên để paste cho khớp baseline, ta quan tâm đến ascent hơn.

    # --- TRƯỜNG HỢP 1: TÊN NGẮN (Vẽ bình thường) ---
    if text_w <= max_width:
        draw = ImageDraw.Draw(overlay_img)
        # Vẽ căn giữa (anchor='ms': Middle Horizontal, BaseLine Vertical)
        draw.text((128, y_baseline), text, font=font, fill=color, anchor="ms")
        print(f"✅ Tên '{text}' ngắn ({text_w:.0f}px), vẽ thường.")

    # --- TRƯỜNG HỢP 2: TÊN DÀI (Bóp dẹt) ---
    else:
        print(f"⚠️ Tên '{text}' dài ({text_w:.0f}px) -> Bóp về {max_width}px.")

        # Tạo canvas tạm đủ rộng để chứa hết tên chưa bóp
        # Chiều cao lấy dư ra chút (font_size * 2) để ko bị cắt ngọn
        temp_h = font_size * 2
        temp_img = Image.new("RGBA", (int(text_w) + 10, temp_h), (0, 0, 0, 0))
        d_temp = ImageDraw.Draw(temp_img)

        # Vẽ text lên canvas tạm.
        # Tọa độ (0, ascent) nghĩa là đặt đường baseline cách đỉnh ảnh một đoạn = ascent
        # Để tí nữa mình cắt cho dễ.
        d_temp.text((0, ascent), text, font=font, fill=color, anchor="ls") # ls = Left Baseline

        # Crop (Cắt) lấy phần vừa khít cái chữ để bóp cho đẹp
        bbox = temp_img.getbbox() # Lấy khung bao quanh chữ
        if bbox:
            cropped_text = temp_img.crop(bbox)

            # Tính kích thước mới
            new_w = max_width # Ép về 156px
            new_h = cropped_text.height # Giữ nguyên chiều cao

            # Bóp ảnh (Resample LANCZOS để chữ ko bị vỡ hạt)
            squashed_text = cropped_text.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Tính tọa độ dán vào ảnh gốc
            # X: Căn giữa -> 128 - (một nửa chiều rộng mới)
            paste_x = 128 - (new_w // 2)

            # Y: Căn theo baseline
            # Lúc nãy ta vẽ baseline ở toạ độ Y = ascent.
            # bbox[1] là toạ độ đỉnh của chữ thực tế.
            # Khoảng cách từ đỉnh chữ đến baseline = ascent - bbox[1]
            offset_from_top_to_baseline = ascent - bbox[1]

            # Tọa độ Y để dán = (Y_baseline mong muốn) - (Khoảng cách từ đỉnh đến baseline)
            paste_y = y_baseline - offset_from_top_to_baseline

            # Dán đè lên (Alpha Composite)
            overlay_img.alpha_composite(squashed_text, (int(paste_x), int(paste_y)))

# --- 3. HÀM XỬ LÝ CHÍNH ---
def process_card_full_option(s_bytes, p_bytes, f_bytes, l_bytes, c_bytes, config):
    print("\n--- Bắt đầu Request (Chế độ Bóp dẹt) ---")

    card_size = (256, 256)
    overlay = Image.new("RGBA", card_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 1. Player
    if p_bytes:
        try:
            player_img = Image.open(io.BytesIO(p_bytes)).convert("RGBA")
            player_img = player_img.resize(card_size, Image.Resampling.LANCZOS)
            overlay.alpha_composite(player_img)
        except: pass

    # 2. Text Data
    ovr_text = str(config.get("text_ovr", "99"))
    pos_text = str(config.get("text_pos", "ST"))
    name_text = str(config.get("text_name", "HUY NGUYEN")).upper().strip()
    text_color = config.get("text_color", "#FFFFFF")

    # Font OVR/POS
    font_ovr = load_font(PATH_STANDARD, 36)
    font_pos = load_font(PATH_STANDARD, 24)

    # Vẽ OVR & POS
    ovr_x, ovr_y = 54, 24
    bbox_ovr = draw.textbbox((ovr_x, ovr_y), ovr_text, font=font_ovr)
    ovr_center_x = (bbox_ovr[0] + bbox_ovr[2]) / 2
    draw.text((ovr_x, ovr_y), ovr_text, font=font_ovr, fill=text_color)

    ovr_height = bbox_ovr[3] - bbox_ovr[1]
    pos_y = ovr_y + ovr_height + 12
    draw.text((ovr_center_x, pos_y), pos_text, font=font_pos, fill=text_color, anchor="ma")

    # --- VẼ NAME BÓP DẸT ---
    # Baseline Y = 256 - 67 = 189
    # Max Width = 156 (như m yêu cầu)
    draw_name_squash(
        overlay_img=overlay, # Truyền cả cái ảnh overlay vào để hàm tự dán
        text=name_text,
        font_path=PATH_NAME, # Dùng font Extended
        color=text_color,
        y_baseline=256 - 70,
        max_width=144        # Ngưỡng bắt đầu bóp
    )
    # -----------------------

    # 3. Icons Logic
    loaded_icons = []
    icon_sources = [f_bytes, l_bytes, c_bytes]
    for source in icon_sources:
        if source:
            try:
                img = Image.open(io.BytesIO(source)).convert("RGBA")
                img = img.resize((24, 24), Image.Resampling.LANCZOS)
                loaded_icons.append(img)
            except: pass

    if loaded_icons:
        icon_size = 24
        gap = 26
        total_width = (len(loaded_icons) * icon_size) + ((len(loaded_icons) - 1) * gap)
        start_x = (256 - total_width) // 2
        start_y = 256 - 44 - icon_size
        curr_x = start_x
        for icon in loaded_icons:
            overlay.alpha_composite(icon, (int(curr_x), int(start_y)))
            curr_x += icon_size + gap

    # 4. Sprite Processing
    try:
        sprite_sheet = Image.open(io.BytesIO(s_bytes)).convert("RGBA")
    except: return None

    cols = int(config.get("cols", 7))
    rows = int(config.get("rows", 7))
    max_frames = int(config.get("max_frames", 45))
    duration = int(config.get("duration", 50))

    sheet_w, sheet_h = sprite_sheet.size
    frame_w = sheet_w // cols
    frame_h = sheet_h // rows

    frames = []
    count = 0

    for r in range(rows):
        for c in range(cols):
            if count >= max_frames: break
            left, top = c * frame_w, r * frame_h
            frame = sprite_sheet.crop((left, top, left + frame_w, top + frame_h))
            if frame.size != card_size:
                frame = frame.resize(card_size, Image.Resampling.LANCZOS)

            final_frame = Image.new("RGBA", card_size)
            final_frame.paste(frame, (0,0))
            final_frame.alpha_composite(overlay)
            frames.append(final_frame)
            count += 1

    output_io = io.BytesIO()
    if frames:
        frames[0].save(output_io, format='WEBP', save_all=True, append_images=frames[1:], duration=duration, loop=0, quality=90)
        output_io.seek(0)
        return output_io
    return None

@app.post("/generate-card")
async def generate_card_api(
    sprite: UploadFile = File(...),
    player: UploadFile = File(None),
    flag: UploadFile = File(None),
    league: UploadFile = File(None),
    club: UploadFile = File(None),
    config: str = Form(...)
):
    try:
        config_dict = json.loads(config)
        if isinstance(config_dict, str): config_dict = json.loads(config_dict)
    except: raise HTTPException(status_code=400, detail="Config lỗi format")

    s_bytes = await sprite.read()
    p_bytes = await player.read() if player else None
    f_bytes = await flag.read() if flag else None
    l_bytes = await league.read() if league else None
    c_bytes = await club.read() if club else None

    result_io = process_card_full_option(s_bytes, p_bytes, f_bytes, l_bytes, c_bytes, config_dict)

    if result_io: return StreamingResponse(result_io, media_type="image/webp")
    else: raise HTTPException(status_code=500, detail="Lỗi xử lý ảnh")

@app.get("/")
def home():
    return {"status": "Running", "fonts": "Loaded" if 'FONT_OVR' in globals() else "Default"}
