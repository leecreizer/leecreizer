"""어드민 앱 스모크 테스트 (로그인 → 각 기능 CRUD → 일괄등록)."""
import io

import pytest

flask = pytest.importorskip("flask")

from admin import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    app = create_app(db_path=tmp_path / "test_admin.db")
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def login(client, username="admin", password="admin1234"):
    return client.post(
        "/login", data={"username": username, "password": password}, follow_redirects=True
    )


def test_login_required_redirect(client):
    res = client.get("/dashboard")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_login_logout(client):
    res = login(client)
    assert res.status_code == 200
    assert "대시보드".encode() in res.data

    res = login(client, password="wrong")
    assert "올바르지 않습니다".encode() in res.data


def test_org_crud(client):
    login(client)
    res = client.post(
        "/org/channels/save",
        data={"code": "B2B", "name": "B2B몰", "description": "", "active": "1"},
        follow_redirects=True,
    )
    assert "추가했습니다".encode() in res.data

    res = client.post(
        "/org/groups/save",
        data={"name": "B2B 운영팀", "channel_id": "1", "active": "1"},
        follow_redirects=True,
    )
    assert "추가했습니다".encode() in res.data

    res = client.post(
        "/org/users/save",
        data={
            "username": "tester", "name": "테스터", "password": "pw1234",
            "role": "manager", "group_id": "1", "active": "1",
        },
        follow_redirects=True,
    )
    assert "추가했습니다".encode() in res.data


def test_category_crud(client):
    login(client)
    res = client.post(
        "/categories/save",
        data={"name": "조명", "parent_id": "", "active": "1", "channel_ids": ["1", "2"]},
        follow_redirects=True,
    )
    assert "추가했습니다".encode() in res.data
    assert "조명".encode() in client.get("/categories/").data


def test_category_save_returns_to_contents_page(client):
    """통합 화면(콘텐츠 관리)에서 폴더 저장 시 해당 화면으로 복귀한다."""
    login(client)
    res = client.post(
        "/categories/save",
        data={"name": "통합폴더", "parent_id": "", "active": "1",
              "channel_ids": ["1"], "next": "/contents/?category_id=1"},
    )
    assert res.status_code == 302
    assert res.headers["Location"] == "/contents/?category_id=1"
    body = client.get("/contents/").data.decode()
    assert "통합폴더" in body  # 좌측 폴더 트리에 노출


def test_content_form_and_master(client):
    login(client)
    res = client.post(
        "/contents/new",
        data={
            "code": "TEST-001", "name": "테스트 책상", "category_id": "3",
            "status": "published", "brand": "테스트브랜드", "price": "150000",
            "width_mm": "1200", "unit": "EA", "tag_ids": ["1", "4"],
        },
        follow_redirects=True,
    )
    assert "저장했습니다".encode() in res.data
    listing = client.get("/contents/?q=TEST-001").data
    assert "테스트 책상".encode() in listing


def test_workspace_detail_panel(client):
    """리스트에서 콘텐츠 선택 시 같은 화면에 마스터 패널이 열린다."""
    login(client)
    body = client.get("/contents/?selected=1").data.decode()
    assert "마스터 정보" in body          # 상세 패널
    assert "BED-001" in body              # 선택된 콘텐츠
    assert "qe1" in body                  # 인라인 빠른 수정 폼

    body = client.get("/contents/?new=1&category_id=3").data.decode()
    assert "새 콘텐츠 등록" in body       # 신규 등록 패널 (카테고리 사전 선택)


def test_quick_update_inline(client):
    """행에서 이름·노출상태 바로 수정."""
    login(client)
    res = client.post(
        "/contents/1/quick",
        data={"name": "이름변경 침대", "status": "hidden", "next": "/contents/?category_id=3"},
    )
    assert res.status_code == 302
    assert res.headers["Location"] == "/contents/?category_id=3"
    body = client.get("/contents/?q=이름변경").data.decode()
    assert "이름변경 침대" in body


def test_detail_panel_save_returns_to_workspace(client):
    """상세 패널 저장 후 워크스페이스(선택 유지)로 복귀."""
    login(client)
    res = client.post(
        "/contents/1/edit",
        data={
            "code": "BED-001", "name": "수면공감 평상형 침대 Q", "category_id": "3",
            "status": "published", "brand": "리브홈", "price": "590000", "unit": "EA",
            "next": "/contents/?category_id=3&selected=1",
        },
    )
    assert res.status_code == 302
    assert res.headers["Location"] == "/contents/?category_id=3&selected=1"
    body = client.get("/contents/?selected=1").data.decode()
    assert "590000" in body  # 저장된 마스터 가격이 패널에 반영


def test_bulk_upload(client):
    login(client)
    csv_data = (
        "콘텐츠코드,콘텐츠명,카테고리경로,상태,브랜드,모델번호,판매가,원가,단위,"
        "가로(mm),세로(mm),높이(mm),재질,색상,제조사,원산지,태그\n"
        "BULK-001,일괄 침대,가구 > 침실 > 침대,노출,리브홈,LH-1,390000,210000,EA,"
        "1200,2050,350,PB,화이트,리브홈산업,대한민국,스타일>모던\n"
        "BULK-002,일괄 신규카테고리 상품,신규대분류 > 신규중분류,숨김,,,,,,,,,,,,,새폴더>새태그\n"
    ).encode("utf-8-sig")
    res = client.post(
        "/contents/bulk",
        data={"file": (io.BytesIO(csv_data), "bulk.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert res.status_code == 200
    body = res.data.decode()
    assert "업로드 결과" in body
    listing = client.get("/contents/?q=BULK").data.decode()
    assert "일괄 침대" in listing
    assert "신규대분류" in listing  # 카테고리 경로 자동 생성 확인


def test_tags_crud(client):
    login(client)
    res = client.post(
        "/tags/folders/save", data={"name": "공간", "active": "1"}, follow_redirects=True
    )
    assert "추가했습니다".encode() in res.data
    res = client.post(
        "/tags/save",
        data={"folder_id": "1", "name": "미니멀", "color": "#000000", "active": "1"},
        follow_redirects=True,
    )
    assert "추가했습니다".encode() in res.data
