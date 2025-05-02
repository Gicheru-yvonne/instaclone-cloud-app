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
from local_constants import PROJECT_NAME, PROJECT_STORAGE_BUCKET


app = FastAPI()

firebase_request_adapter = google_requests.Request()
db = firestore.Client()  



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

    
    bucket = storage.Client(project=PROJECT_NAME).bucket(PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(f"posts/{username}_{datetime.utcnow().isoformat()}_{image.filename}")
    blob.upload_from_file(image.file, content_type=image.content_type)
    blob.make_public()  

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

   
    following = user_data.get("following", [])
    if not any(f["uid"] == target_uid for f in following):
        following.append({
            "uid": target_uid,
            "timestamp": datetime.utcnow().isoformat()
        })
        user_ref.update({"following": following})

    
    followers = target_data.get("followers", [])
    if not any(f["uid"] == current_uid for f in followers):
        followers.append({
            "uid": current_uid,
            "timestamp": datetime.utcnow().isoformat()
        })
        target_ref.update({"followers": followers})

    return {"message": f"Now following user {target_uid}"}


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    try:
        decoded = verify_token(request)
        username = decoded.get("email").split("@")[0].lower()
        uid = decoded.get("uid") or decoded.get("sub")

        # ✅ Get the posts for the current user
        posts_query = (
            db.collection("Post")
            .where("Username", "==", username)
            .order_by("Date", direction=firestore.Query.DESCENDING)
            .stream()
        )
        posts = [post.to_dict() for post in posts_query]

        # ✅ Get followers and following from the 'User' collection
        user_doc = db.collection("User").document(uid).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            followers = user_data.get("followers", [])
            following = user_data.get("following", [])
        else:
            followers = []
            following = []

        # ✅ Pass followers_count and following_count to the template
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "posts": posts,
            "username": username,
            "followers_count": len(followers),
            "following_count": len(following)
        })

    except Exception as e:
        print("❌ Error fetching profile posts:", e)
        return RedirectResponse("/login")

@app.get("/followers", response_class=HTMLResponse)
async def followers_page(request: Request):
    try:
        decoded = verify_token(request)
        uid = decoded.get("uid") or decoded.get("sub")

        user_doc = db.collection("User").document(uid).get()
        followers = user_doc.to_dict().get("followers", []) if user_doc.exists else []

       
        followers = sorted(followers, key=lambda x: x["timestamp"], reverse=True)

        # Fetch follower emails or info
        follower_details = []
        for follower in followers:
            follower_uid = follower["uid"]
            doc = db.collection("User").document(follower_uid).get()
            if doc.exists:
                follower_details.append(doc.to_dict().get("email"))

        return templates.TemplateResponse("followers.html", {
            "request": request,
            "followers": follower_details
        })
    except:
        return RedirectResponse("/login")


@app.get("/following", response_class=HTMLResponse)
async def following_page(request: Request):
    try:
        decoded = verify_token(request)
        uid = decoded.get("uid") or decoded.get("sub")

        user_doc = db.collection("User").document(uid).get()
        following = user_doc.to_dict().get("following", []) if user_doc.exists else []

        
        following = sorted(following, key=lambda x: x["timestamp"], reverse=True)

        # Fetch following emails or info
        following_details = []
        for following_user in following:
            following_uid = following_user["uid"]
            doc = db.collection("User").document(following_uid).get()
            if doc.exists:
                following_details.append(doc.to_dict().get("email"))

        return templates.TemplateResponse("following.html", {
            "request": request,
            "following": following_details
        })
    except:
        return RedirectResponse("/login")

@app.get("/user/{target_uid}", response_class=HTMLResponse)
async def view_user_profile(request: Request, target_uid: str):
    try:
        decoded = verify_token(request)
        current_uid = decoded.get("uid") or decoded.get("sub")

        # Redirect if user is viewing their own profile
        if current_uid == target_uid:
            return RedirectResponse("/profile")

        # Get target user data
        target_doc = db.collection("User").document(target_uid).get()
        if not target_doc.exists:
            return JSONResponse(status_code=404, content={"error": "User not found"})
        target_data = target_doc.to_dict()
        target_email = target_data.get("email")
        target_username = target_email.split("@")[0].lower()

        # Get target user's posts
        posts_query = (
            db.collection("Post")
            .where("Username", "==", target_username)
            .order_by("Date", direction=firestore.Query.DESCENDING)
            .stream()
        )
        posts = [post.to_dict() for post in posts_query]

        # Followers & following count
        followers = target_data.get("followers", [])
        following = target_data.get("following", [])

        # Check if current user follows target user
        current_user_doc = db.collection("User").document(current_uid).get()
        is_following = False
        if current_user_doc.exists:
            current_user_data = current_user_doc.to_dict()
            is_following = any(f["uid"] == target_uid for f in current_user_data.get("following", []))

        return templates.TemplateResponse("user_profile.html", {
            "request": request,
            "target_uid": target_uid,
            "target_email": target_email,
            "is_following": is_following,
            "posts": posts,
            "followers_count": len(followers),
            "following_count": len(following)
        })

    except Exception as e:
        print("❌ Error loading user profile:", e)
        return RedirectResponse("/login")



@app.post("/unfollow")
async def unfollow_user(request: Request, target_uid: str = Form(...)):
    try:
        decoded = verify_token(request)
    except:
        return RedirectResponse("/login", status_code=302)

    current_uid = decoded.get("sub")
    user_ref = db.collection("User").document(current_uid)
    target_ref = db.collection("User").document(target_uid)

    user_doc = user_ref.get()
    target_doc = target_ref.get()

    if not user_doc.exists or not target_doc.exists:
        return JSONResponse(status_code=404, content={"error": "User not found"})

    user_data = user_doc.to_dict()
    target_data = target_doc.to_dict()

    # Remove from following
    following = user_data.get("following", [])
    following = [f for f in following if f["uid"] != target_uid]
    user_ref.update({"following": following})

    # Remove from followers
    followers = target_data.get("followers", [])
    followers = [f for f in followers if f["uid"] != current_uid]
    target_ref.update({"followers": followers})

    return {"message": f"Unfollowed user {target_uid}"}

@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    try:
        verify_token(request)
        return templates.TemplateResponse("search.html", {"request": request})
    except:
        return RedirectResponse("/login")

@app.get("/search_results", response_class=HTMLResponse)
async def search_results(request: Request, query: str):
    try:
        decoded = verify_token(request)
        results = []

        # 🔥 Query users where the email starts with the search query
        users = db.collection("User").stream()
        for user in users:
            user_data = user.to_dict()
            email = user_data.get("email", "")
            profile_name = email.split("@")[0].lower()

            if profile_name.startswith(query.lower()):
                results.append({
                    "uid": user_data.get("uid"),
                    "email": email
                })

        return templates.TemplateResponse("search_results.html", {
            "request": request,
            "results": results,
            "query": query
        })

    except Exception as e:
        print("❌ Error during search:", e)
        return RedirectResponse("/login")

@app.get("/timeline", response_class=HTMLResponse)
async def timeline_page(request: Request):
    try:
        decoded = verify_token(request)
        uid = decoded.get("uid") or decoded.get("sub")
        username = decoded.get("email").split("@")[0].lower()

        user_doc = db.collection("User").document(uid).get()
        if not user_doc.exists:
            return RedirectResponse("/profile")

        user_data = user_doc.to_dict()
        following = user_data.get("following", [])

        usernames = [username]
        for entry in following:
            following_uid = entry.get("uid")
            doc = db.collection("User").document(following_uid).get()
            if doc.exists:
                email = doc.to_dict().get("email", "")
                follow_username = email.split("@")[0].lower()
                usernames.append(follow_username)

        posts = []
        for user in usernames:
            query = (
                db.collection("Post")
                .where("Username", "==", user)
                .stream()
            )
            for doc in query:
                post_data = doc.to_dict()
                post_data["id"] = doc.id

                # Fetch recent comments for this post
                comments_query = (
                    db.collection("Post")
                    .document(doc.id)
                    .collection("Comments")
                    .order_by("timestamp", direction=firestore.Query.DESCENDING)
                    .limit(5)
                    .stream()
                )
                comments = []
                for c in comments_query:
                    c_data = c.to_dict()
                    c_data["username"] = c_data.get("author", "").split("@")[0]
                    comments.append(c_data)

                post_data["comments"] = comments
                posts.append(post_data)

        posts = sorted(posts, key=lambda p: p.get("Date", ""), reverse=True)[:50]

        return templates.TemplateResponse("timeline.html", {
            "request": request,
            "posts": posts
        })

    except Exception as e:
        print("❌ Error loading timeline:", e)
        return RedirectResponse("/login")


@app.post("/comment")
async def add_comment(request: Request, post_id: str = Form(...), text: str = Form(...)):
    try:
        decoded = verify_token(request)
        author = decoded.get("email")
        
        if len(text) > 200:
            raise HTTPException(status_code=400, detail="Comment too long")

        comment_data = {
            "text": text,
            "author": author,
            "timestamp": datetime.utcnow().isoformat()
        }

        db.collection("Post").document(post_id).collection("Comments").add(comment_data)

        return RedirectResponse("/timeline", status_code=302)
    except Exception as e:
        print("❌ Error adding comment:", e)
        return RedirectResponse("/login")