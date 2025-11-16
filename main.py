import os
import io
import random
from typing import List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import db, create_document

# ----- App Setup -----
app = FastAPI(title="ViralQuoteMachine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Utilities -----
CATEGORIES = ["motivational", "love", "business", "fitness", "funny"]
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1200, 1500

SAFE_BEIGE = (238, 232, 223)
GRADIENTS = [
    ((245, 240, 232), (222, 203, 182)),
    ((250, 242, 234), (221, 214, 200)),
    ((240, 235, 226), (210, 200, 190)),
    ((255, 247, 240), (232, 222, 210)),
]

BOLD_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]
LIGHT_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]

AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "yourtag-20")


def build_affiliate_links(text: str) -> List[str]:
    base = "https://www.amazon.com/s?k="
    keywords = [
        f"motivational+books&tag={AFFILIATE_TAG}",
        f"journals&tag={AFFILIATE_TAG}",
        f"poster+frame&tag={AFFILIATE_TAG}",
    ]
    return [f"{base}{k}" for k in keywords]


# ----- Image Rendering (Pillow if available, otherwise SVG fallback) -----

def pil_available() -> bool:
    try:
        import PIL  # noqa: F401
        return True
    except Exception:
        return False


def render_quote_image_with_pil(text: str, author: Optional[str], watermark: bool, quality: str = "standard", width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT):
    from PIL import Image, ImageDraw, ImageFont  # import lazily

    def draw_vertical_gradient(img, top_rgb, bottom_rgb):
        draw = ImageDraw.Draw(img)
        for y in range(img.height):
            ratio = y / img.height
            r = int(top_rgb[0] * (1 - ratio) + bottom_rgb[0] * ratio)
            g = int(top_rgb[1] * (1 - ratio) + bottom_rgb[1] * ratio)
            b = int(top_rgb[2] * (1 - ratio) + bottom_rgb[2] * ratio)
            draw.line([(0, y), (img.width, y)], fill=(r, g, b))

    def fit_text(draw, text, font_path, max_width, max_font_size):
        size = max_font_size
        while size > 18:
            font = ImageFont.truetype(font_path, size)
            w, _ = draw.multiline_textsize(text, font=font, spacing=8)
            if w <= max_width:
                return font
            size -= 2
        return ImageFont.truetype(font_path, 18)

    img = Image.new("RGB", (width, height), SAFE_BEIGE)
    gtop, gbottom = random.choice(GRADIENTS)
    draw_vertical_gradient(img, gtop, gbottom)
    draw = ImageDraw.Draw(img)

    font_bold_path = next((f for f in BOLD_FONTS if os.path.exists(f)), BOLD_FONTS[0])
    font_light_path = next((f for f in LIGHT_FONTS if os.path.exists(f)), LIGHT_FONTS[0])

    margin = int(width * 0.08)
    max_text_width = width - margin * 2

    quote_font = fit_text(draw, text, font_bold_path, max_text_width, int(width * 0.10))
    author_font = ImageFont.truetype(font_light_path, int(width * 0.035))

    # Wrap text manually
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        tw, _ = draw.textsize(test, font=quote_font)
        if tw <= max_text_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)

    total_text_height = sum([draw.textsize(line, font=quote_font)[1] for line in lines]) + (len(lines) - 1) * 10

    y = (height - total_text_height) // 2
    for line in lines:
        lw, lh = draw.textsize(line, font=quote_font)
        x = (width - lw) // 2
        draw.text((x, y), line, font=quote_font, fill=(30, 30, 30))
        y += lh + 10

    if author:
        aw, ah = draw.textsize(f"— {author}", font=author_font)
        draw.text(((width - aw) // 2, y + int(height * 0.02)), f"— {author}", font=author_font, fill=(60, 60, 60))

    if watermark:
        wm_font = ImageFont.truetype(font_light_path, int(width * 0.035))
        wm_text = "ViralQuoteMachine.com"
        tw, th = draw.textsize(wm_text, wm_font)
        draw.text((width - tw - margin, height - th - margin), wm_text, font=wm_font, fill=(80, 80, 80))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), "image/png"


def render_quote_svg(text: str, author: Optional[str], watermark: bool, width: int = 1200, height: int = 1500):
    bg = "#F5EFE6"
    fg = "#2e2a27"
    sub = "#4b463f"
    # Basic escaping for XML special chars
    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    author_text = f"<text x='50%' y='65%' fill='{sub}' font-family='sans-serif' font-size='36' text-anchor='middle'>— {esc(author)}</text>" if author else ""
    wm = ""
    if watermark:
        wm = f"<text x='{width-40}' y='{height-40}' fill='{sub}' font-family='sans-serif' font-size='36' text-anchor='end'>ViralQuoteMachine.com</text>"

    svg = f"""
    <svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
      <defs>
        <linearGradient id='g' x1='0' y1='0' x2='0' y2='1'>
          <stop offset='0%' stop-color='#faf2ea'/>
          <stop offset='100%' stop-color='#e5d8c9'/>
        </linearGradient>
      </defs>
      <rect width='100%' height='100%' fill='url(#g)'/>
      <foreignObject x='80' y='20%' width='{width-160}' height='50%'>
        <div xmlns='http://www.w3.org/1999/xhtml' style='font-family:sans-serif;color:{fg};font-size:64px;line-height:1.2;text-align:center;font-weight:800;'>
          {esc(text)}
        </div>
      </foreignObject>
      {author_text}
      {wm}
    </svg>
    """.strip()
    return svg.encode("utf-8"), "image/svg+xml"


# ----- Data Models -----
class GenerateRequest(BaseModel):
    text: Optional[str] = None
    category: Optional[str] = Field(default="motivational")
    author: Optional[str] = None
    premium: bool = False

class QuoteOut(BaseModel):
    id: str
    text: str
    category: str
    author: Optional[str]
    image_url: str
    affiliate_links: List[str]
    likes: int
    views: int
    created_at: Optional[str] = None


# ----- Quote Generation Logic -----
STARTS = [
    "Dream big.",
    "Progress beats perfection.",
    "Stay consistent.",
    "Love loudly.",
    "Hustle quietly.",
    "Laugh often.",
]
MIDDLES = [
    "Every day is a fresh page.",
    "Tiny steps compound into greatness.",
    "Your future self is watching.",
    "Energy flows where focus goes.",
    "Discipline is a form of self-love.",
    "Make it fun and it lasts.",
]
ENDS = [
    "Start now.",
    "Own your story.",
    "You are the advantage.",
    "Design your day.",
    "Share the joy.",
    "Let momentum carry you.",
]


def generate_original_quote(category: str) -> str:
    parts = [random.choice(STARTS), random.choice(MIDDLES), random.choice(ENDS)]
    base = " ".join(parts)
    if category == "business":
        base += " Build value, not vanity."
    if category == "fitness":
        base += " Sweat is an investment."
    if category == "love":
        base += " Choose each other daily."
    if category == "funny":
        base += " Coffee first, ambition second."
    return base


# ----- Routes -----
@app.get("/")
def root():
    return {"name": "ViralQuoteMachine API", "message": "Running", "hourly": True}


@app.get("/api/quotes", response_model=List[QuoteOut])
def list_quotes(skip: int = 0, limit: int = 30):
    items = db["quote"].find({}).sort("created_at", -1).skip(skip).limit(limit)
    results: List[QuoteOut] = []
    for it in items:
        _id = str(it.get("_id"))
        results.append(
            QuoteOut(
                id=_id,
                text=it.get("text"),
                category=it.get("category"),
                author=it.get("author"),
                image_url=f"/image/{_id}",
                affiliate_links=it.get("affiliate_links", []),
                likes=it.get("likes", 0),
                views=it.get("views", 0),
                created_at=str(it.get("created_at")),
            )
        )
    return results


@app.get("/api/quotes/{quote_id}")
def get_quote(quote_id: str):
    from bson import ObjectId
    q = db["quote"].find_one({"_id": ObjectId(quote_id)})
    if not q:
        raise HTTPException(404, "Quote not found")
    q["id"] = str(q.pop("_id"))
    q["image_url"] = f"/image/{q['id']}"
    return q


@app.post("/api/quotes/generate", response_model=QuoteOut)
def generate_quote(req: GenerateRequest):
    category = req.category if req.category in CATEGORIES else "motivational"
    text = req.text.strip() if req.text else generate_original_quote(category)
    author = req.author
    watermark = not req.premium

    aff = build_affiliate_links(text)

    quote_doc = {
        "text": text,
        "category": category,
        "author": author,
        "watermark": watermark,
        "quality": "high" if req.premium else "standard",
        "affiliate_links": aff,
        "likes": 0,
        "views": 0,
        "posted": False,
        "platforms": [],
        "seo_title": f"{text[:60]} | {category.title()} Quote",
        "seo_description": text,
    }
    new_id = create_document("quote", quote_doc)

    return QuoteOut(
        id=new_id,
        text=text,
        category=category,
        author=author,
        image_url=f"/image/{new_id}",
        affiliate_links=aff,
        likes=0,
        views=0,
    )


@app.get("/image/{quote_id}")
def serve_quote_image(quote_id: str):
    from bson import ObjectId
    q = db["quote"].find_one({"_id": ObjectId(quote_id)})
    if not q:
        raise HTTPException(404, "Quote not found")

    text = q.get("text")
    author = q.get("author")
    watermark = bool(q.get("watermark", True))

    if pil_available():
        try:
            content, media = render_quote_image_with_pil(text, author, watermark, q.get("quality", "standard"))
            return Response(content=content, media_type=media)
        except Exception:
            pass
    # Fallback to SVG
    content, media = render_quote_svg(text, author, watermark)
    return Response(content=content, media_type=media)


# ----- Subscribers & Digest -----
class SubscribeRequest(BaseModel):
    email: str

@app.post("/api/subscribe")
def subscribe(req: SubscribeRequest):
    if not req.email or "@" not in req.email:
        raise HTTPException(400, "Invalid email")
    existing = db["subscriber"].find_one({"email": req.email})
    if existing:
        return {"status": "ok", "message": "Already subscribed"}
    create_document("subscriber", {"email": req.email, "active": True, "created_from": "web"})
    return {"status": "ok"}


# ----- Billing (Stripe) -----
STRIPE_SECRET = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")

@app.post("/api/billing/create-checkout-session")
def create_checkout_session():
    if not STRIPE_SECRET or not STRIPE_PRICE_ID:
        raise HTTPException(400, "Billing not configured")
    import stripe
    stripe.api_key = STRIPE_SECRET
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
            success_url=os.getenv("PUBLIC_SITE_URL", "http://localhost:3000") + "/?upgraded=true",
            cancel_url=os.getenv("PUBLIC_SITE_URL", "http://localhost:3000") + "/pricing",
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(500, str(e))


# ----- Posting Stubs -----

def post_to_platforms(quote_doc: dict):
    pinterest_token = os.getenv("PINTEREST_ACCESS_TOKEN")
    instagram_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    threads_token = os.getenv("THREADS_ACCESS_TOKEN")
    platforms = []
    if pinterest_token:
        platforms.append("pinterest")
    if instagram_token:
        platforms.append("instagram")
    if threads_token:
        platforms.append("threads")
    return platforms


# ----- Scheduler -----
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler(timezone="UTC")


def hourly_generation_job():
    try:
        from bson import ObjectId
        for _ in range(30):
            category = random.choice(CATEGORIES)
            text = generate_original_quote(category)
            doc = {
                "text": text,
                "category": category,
                "author": None,
                "watermark": True,
                "quality": "standard",
                "affiliate_links": build_affiliate_links(text),
                "likes": 0,
                "views": 0,
                "posted": False,
                "platforms": [],
                "seo_title": f"{text[:60]} | {category.title()} Quote",
                "seo_description": text,
            }
            _id = create_document("quote", doc)
            platforms = post_to_platforms(doc)
            if platforms:
                db["quote"].update_one({"_id": ObjectId(_id)}, {"$set": {"posted": True, "platforms": platforms}})
    except Exception as e:
        print("Hourly job error:", e)


def daily_digest_job():
    try:
        since = datetime.utcnow() - timedelta(days=1)
        best = db["quote"].find({"created_at": {"$gte": since}}).sort("views", -1).limit(10)
        count = db["subscriber"].count_documents({"active": True})
        print(f"Daily digest prepared for {count} subscribers. Top quotes: {[b.get('text')[:30] for b in best]}")
    except Exception as e:
        print("Daily digest error:", e)


scheduler.add_job(hourly_generation_job, "interval", hours=1, id="hourly_generate", max_instances=1, replace_existing=True)
scheduler.add_job(daily_digest_job, "cron", hour=0, minute=0, id="daily_digest", replace_existing=True)


@app.on_event("startup")
def on_startup():
    try:
        if not scheduler.running:
            scheduler.start()
            print("Scheduler started")
    except Exception as e:
        print("Scheduler failed:", e)


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
