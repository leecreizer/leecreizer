"""어드민 관리 시스템 실행 스크립트.

사용법:
    pip install flask
    python run_admin.py
    → http://localhost:5050 접속 (초기 계정: admin / admin1234)
"""
from admin import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)
