# Sử dụng Python 3.9 bản rút gọn (nhẹ, build nhanh)
FROM python:3.9-slim

# Thiết lập thư mục làm việc trong container
WORKDIR /app

# Copy file requirements trước để tận dụng cache của Docker
COPY requirements.txt .

# Cài đặt các thư viện cần thiết
# --no-cache-dir để giảm dung lượng image
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ code (main.py, folder fonts...) vào container
COPY . .

# Mở port 8000 (Port mặc định của Uvicorn)
EXPOSE 8000

# Lệnh chạy server khi container khởi động
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
