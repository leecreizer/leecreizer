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


def test_api_categories(client):
    """설계 페이지 연동: 채널별 노출 카테고리 트리 (인증 불필요)."""
    res = client.get("/api/channels/DIRECT/categories")
    assert res.status_code == 200
    data = res.get_json()
    assert data["channel"]["code"] == "DIRECT"
    names = [c["name"] for c in data["categories"]]
    assert "가구" in names and "주방" in names

    assert client.get("/api/channels/NOPE/categories").status_code == 404


def test_api_categories_respects_exposure(client):
    """채널 노출을 끄면 해당 카테고리(하위 포함)가 API에서 빠진다."""
    login(client)
    # '가구'(id=1)를 DIRECT(채널 1)에서 미노출로 변경 (채널 2,3만 체크)
    client.post(
        "/categories/save",
        data={"id": "1", "name": "가구", "parent_id": "", "active": "1",
              "channel_ids": ["2", "3"]},
    )
    data = client.get("/api/channels/DIRECT/categories").get_json()
    names = [c["name"] for c in data["categories"]]
    assert "가구" not in names and "주방" in names
    # 다른 채널에서는 여전히 노출
    data2 = client.get("/api/channels/PARTNER/categories").get_json()
    assert "가구" in [c["name"] for c in data2["categories"]]


def test_api_contents_published_only(client):
    """노출(published) 콘텐츠만, 마스터·태그 포함해 내려간다."""
    res = client.get("/api/channels/DIRECT/contents")
    assert res.status_code == 200
    data = res.get_json()
    codes = [i["code"] for i in data["items"]]
    assert "BED-001" in codes and "SOFA-001" in codes
    assert "SINK-001" not in codes  # draft 제외
    bed = next(i for i in data["items"] if i["code"] == "BED-001")
    assert bed["master"]["brand"] == "리브홈"
    assert any(t["name"] == "모던" for t in bed["tags"])

    # 태그 필터 (AND)
    data = client.get("/api/channels/DIRECT/contents?tag=모던").get_json()
    assert [i["code"] for i in data["items"]] == ["BED-001"]


def test_export_csv_roundtrip_format(client):
    """내보내기 CSV가 일괄등록 템플릿과 같은 컬럼/값 형식이다."""
    login(client)
    res = client.get("/contents/export")
    assert res.status_code == 200
    assert "text/csv" in res.headers["Content-Type"]
    body = res.data.decode("utf-8-sig")
    assert body.splitlines()[0].startswith("콘텐츠코드,콘텐츠명,카테고리경로")
    assert "BED-001" in body
    assert "가구 > 침실 > 침대" in body
    assert "스타일>모던" in body


def test_rbac_viewer_readonly_and_org_admin_only(client):
    """조회자는 변경 불가, 관리자 외에는 조직 관리 접근 불가."""
    login(client)
    client.post(
        "/org/users/save",
        data={"username": "viewer1", "name": "조회자", "password": "pw1234",
              "role": "viewer", "group_id": "1", "active": "1"},
    )
    client.get("/logout")
    login(client, "viewer1", "pw1234")

    # 읽기는 가능
    assert client.get("/contents/").status_code == 200
    # 쓰기는 차단
    res = client.post(
        "/tags/folders/save", data={"name": "차단테스트", "active": "1"},
        follow_redirects=True,
    )
    assert "변경할 수 없습니다".encode() in res.data
    body = client.get("/tags/").data.decode()
    assert "차단테스트" not in body
    # 조직 관리는 관리자 전용
    res = client.get("/org/", follow_redirects=True)
    assert "관리자만 접근할 수 있습니다".encode() in res.data


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
