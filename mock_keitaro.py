from fastapi import FastAPI, HTTPException

app = FastAPI(title="Keitaro — локальная заглушка")

offers = [
    {"id": 101, "name": "Тестовый оффер A"},
    {"id": 102, "name": "Тестовый оффер B"},
    {"id": 103, "name": "Тестовый оффер C"},
    {"id": 104, "name": "Тестовый оффер D"},
    {"id": 105, "name": "Тестовый оффер E"},
]
campaigns = {}
streams = {}


@app.get("/admin_api/v1/offers")
def list_offers():
    return offers


@app.get("/admin_api/v1/campaigns")
def list_campaigns(limit: int = 100, offset: int = 0):
    return list(campaigns.values())[offset:offset + limit]


@app.post("/admin_api/v1/campaigns")
def create_campaign(body: dict):
    campaign_id = max(campaigns, default=900000) + 1
    campaign = {**body, "id": campaign_id}
    campaigns[campaign_id] = campaign
    return campaign


@app.post("/admin_api/v1/campaigns/{campaign_id}/enable")
def enable_campaign(campaign_id: int):
    if campaign_id not in campaigns:
        raise HTTPException(404, "Кампания не найдена")
    campaigns[campaign_id]["state"] = "active"
    return campaigns[campaign_id]


@app.post("/admin_api/v1/streams")
def create_stream(body: dict):
    if body["campaign_id"] not in campaigns:
        raise HTTPException(404, "Кампания не найдена")
    stream_id = max(streams, default=990000) + 1
    stream = {"offers": [], **body, "id": stream_id}
    streams[stream_id] = stream
    return stream


@app.get("/admin_api/v1/campaigns/{campaign_id}/streams")
def list_streams(campaign_id: int):
    if campaign_id not in campaigns:
        raise HTTPException(404, "Кампания не найдена")
    return [
        stream for stream in streams.values()
        if stream["campaign_id"] == campaign_id
    ]


@app.get("/admin_api/v1/streams/{stream_id}")
def get_stream(stream_id: int):
    if stream_id not in streams:
        raise HTTPException(404, "Поток не найден")
    return streams[stream_id]


@app.put("/admin_api/v1/streams/{stream_id}")
def update_stream(stream_id: int, body: dict):
    stream = get_stream(stream_id)
    stream["offers"] = body["offers"]
    return stream