from fastapi import FastAPI, Request, Form, HTTPException, Body, Header
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.cloud import firestore
from datetime import datetime
from fastapi import UploadFile, File
from google.cloud import storage


app = FastAPI()

firebase_request_adapter = google_requests.Request()
db = firestore.Client()  
bucket_name = "my-project-yvonne-452209.appspot.com"
storage_client = storage.Client()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def verify_token(request: Request = None, token: str = None):
    if request:
        token = request.cookies.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        return id_token.verify_firebase_token(token, firebase_request_adapter)
    except Exception as e:
        print("❌ Invalid token:", e)
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    token = request.cookies.get("token")
    user_logged_in = False
    user_email = None

    if token:
        try:
            decoded = id_token.verify_firebase_token(token, firebase_request_adapter)
            user_logged_in = True
            user_email = decoded.get("email")  
        except:
            user_logged_in = False

    return templates.TemplateResponse("main.html", {
        "request": request,
        "logged_in": user_logged_in,
        "user_email": user_email
    })





@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get("token")
    if token:
        try:
            id_token.verify_firebase_token(token, firebase_request_adapter)  
            return RedirectResponse("/")  
        except:
            pass
    return templates.TemplateResponse("login.html", {"request": request})



@app.post("/auth/login")
async def login_user(idToken: str = Form(...)):
    try:
        decoded = id_token.verify_firebase_token(idToken, firebase_request_adapter)
        uid = decoded.get("uid") or decoded.get("sub")
        email = decoded.get("email")

        # ✅ Check if user exists in Firestore
        user_ref = db.collection("User").document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # Initialize their model
            user_ref.set({
                "uid": uid,
                "email": email,
                "following": [],
                "followers": []
            })
            print(f"✅ New user initialized in Firestore: {email}")
        else:
            print(f"🔄 User already exists: {email}")

        # Set the cookie and redirect
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie("token", idToken, httponly=True)
        return response

    except Exception as e:
        print("❌ Login token verification failed:", e)
        return JSONResponse(status_code=401, content={"error": "Invalid token"})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    try:
        verify_token(request)
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except:
        return RedirectResponse("/login")


@app.get("/logout")
async def logout():
    response = RedirectResponse("/login")
    response.delete_cookie("token")
    return response


@app.post("/save_user")
async def save_user(payload: dict = Body(...), authorization: str = Header(None)):
    token = authorization.split(" ")[1] if authorization and authorization.startswith("Bearer ") else None
    if not token:
        return JSONResponse(status_code=401, content={"error": "Missing or malformed token"})

    try:
        decoded = id_token.verify_firebase_token(token, firebase_request_adapter)
    except Exception as e:
        print("❌ Token verification failed:", e)
        return JSONResponse(status_code=401, content={"error": "Invalid token"})

    uid = decoded.get("uid") or decoded.get("sub")
    email = payload.get("email")

    if not uid or not email:
        return JSONResponse(status_code=400, content={"error": "UID and email are required"})

   
    db.collection("User").document(uid).set({
        "uid": uid,
        "email": email,
        "following": [],
        "followers": []
    }, merge=True)

    print("✅ Saved (or updated) user to Firestore without overwriting:", {"uid": uid, "email": email})
    return {"message": "User saved or updated successfully"}


@app.get("/create_post", response_class=HTMLResponse)
async def create_post_form(request: Request):
    return templates.TemplateResponse("create_post.html", {"request": request})

@app.post("/create_post")
async def create_post(
    request: Request,
    caption: str = Form(...),
    image: UploadFile = File(...)
):
    try:
        decoded = verify_token(request)
    except:
        return RedirectResponse("/login", status_code=302)

    username = decoded.get("email").split("@")[0].lower()

    
    if image.content_type not in ["image/png", "image/jpeg"]:
        raise HTTPException(status_code=400, detail="Only PNG and JPG images are allowed.")

    # ✅ Upload to Google Cloud Storage
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f"posts/{username}_{datetime.utcnow().isoformat()}_{image.filename}")
    blob.upload_from_file(image.file, content_type=image.content_type)
    blob.make_public()  # Make the image public so you can view it

    image_url = blob.public_url

    # ✅ Save post metadata in Firestore
    db.collection("Post").add({
        "Username": username,
        "Date": datetime.utcnow().isoformat(),
        "Caption": caption,
        "ImageURL": image_url
    })

    print(f"✅ Post saved for {username} with image: {image_url}")
    return RedirectResponse("/profile", status_code=302)

@app.get("/follow", response_class=HTMLResponse)
async def follow_form(request: Request):
    return templates.TemplateResponse("follow.html", {"request": request})

@app.post("/follow")
async def follow_user(request: Request, target_uid: str = Form(...)):
    try:
        decoded = verify_token(request)
    except:
        return RedirectResponse("/login", status_code=302)

    current_uid = decoded.get("sub")

    if not current_uid or not target_uid or current_uid == target_uid:
        return JSONResponse(status_code=400, content={"error": "Invalid target"})

    user_ref = db.collection("User").document(current_uid)
    target_ref = db.collection("User").document(target_uid)

    # Fetch both documents
    user_doc = user_ref.get()
    target_doc = target_ref.get()

    if not user_doc.exists or not target_doc.exists:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    user_data = user_doc.to_dict()
    target_data = target_doc.to_dict()

    # Update following list
    following = user_data.get("following", [])
    if target_uid not in following:
        following.append(target_uid)
        user_ref.update({"following": following})

    # Update target's followers list
    followers = target_data.get("followers", [])
    if current_uid not in followers:
        followers.append(current_uid)
        target_ref.update({"followers": followers})

    return {"message": f"Now following user {target_uid}"}


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    try:
        decoded = verify_token(request)
        username = decoded.get("email").split("@")[0].lower()  

        
        posts_query = (
            db.collection("Post")
            .where("Username", "==", username)
            .order_by("Date", direction=firestore.Query.DESCENDING)
            .stream()
        )

        posts = [post.to_dict() for post in posts_query]

        return templates.TemplateResponse("profile.html", {
            "request": request,
            "posts": posts,
            "username": username
        })

    except Exception as e:
        print("❌ Error fetching profile posts:", e)
        return RedirectResponse("/login")

