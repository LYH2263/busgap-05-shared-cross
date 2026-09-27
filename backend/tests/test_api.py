from fastapi.testclient import TestClient
from app.main import app

def test_shared_stop_cross_line_flow():
    with TestClient(app) as client:
        lines = client.get("/api/lines").json()
        b12 = next(l for l in lines if l["code"] == "B12")
        k7 = next(l for l in lines if l["code"] == "K7")
        # 默认没有任何共用站：不是所有站都跨线
        assert b12["shared_stops"] == [] and k7["shared_stops"] == []

        # 未登记共用站：只检本线，无跨线事件
        ev = client.post(f"/api/reports/run?line_id={b12['id']}").json()["events"]
        assert not any(e["cross_line"] for e in ev)
        own_count = len(ev)

        # 单方登记不足以启用跨线
        client.put(f"/api/lines/{b12['id']}/shared_stops", json={"stop_names": ["市民中心"]})
        ev = client.post(f"/api/reports/run?line_id={b12['id']}").json()["events"]
        assert not any(e["cross_line"] for e in ev)

        # 双方登记同一站名后，共用站并入他线到站
        client.put(f"/api/lines/{k7['id']}/shared_stops", json={"stop_names": ["市民中心"]})
        lines = client.get("/api/lines").json()
        # 离开再进来仍在：重新拉取仍有登记
        assert next(l for l in lines if l["code"] == "B12")["shared_stops"] == ["市民中心"]
        assert next(l for l in lines if l["code"] == "K7")["shared_stops"] == ["市民中心"]

        ev = client.post(f"/api/reports/run?line_id={b12['id']}").json()["events"]
        cross = [e for e in ev if e["cross_line"]]
        assert cross, "登记共用站后应出现跨线事件"
        assert all(e["stop_name"] == "市民中心" for e in cross)
        assert all(e["other_line"] == "K7" for e in cross)
        assert any(e["status"] == "bunching" for e in cross)
        # 本线内部的串车和大间隔仍然保留
        own = [e for e in ev if not e["cross_line"]]
        assert len(own) == own_count
        assert any(e["status"] == "bunching" for e in own)
        assert any(e["status"] == "large_gap" for e in own)
        # 非共用站只检本线：不出现跨线事件
        assert all(not e["cross_line"] for e in ev if e["stop_name"] != "市民中心")

        # 取消登记后恢复只检本线
        client.put(f"/api/lines/{b12['id']}/shared_stops", json={"stop_names": []})
        ev = client.post(f"/api/reports/run?line_id={b12['id']}").json()["events"]
        assert not any(e["cross_line"] for e in ev)

def test_shared_stops_404_and_normalize():
    with TestClient(app) as client:
        assert client.put("/api/lines/9999/shared_stops", json={"stop_names": []}).status_code == 404
        lines = client.get("/api/lines").json()
        k7 = next(l for l in lines if l["code"] == "K7")
        r = client.put(f"/api/lines/{k7['id']}/shared_stops",
                       json={"stop_names": [" 市民中心 ", "市民中心", "", "火车站"]})
        assert r.status_code == 200
        assert r.json()["shared_stops"] == ["市民中心", "火车站"]
