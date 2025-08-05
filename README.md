 Instagram-style App Clone (Cloud Computing)

This is a simplified replica of Instagram built as part of a Cloud Platforms & Applications module. It allows users to create image-based posts, follow each other, and view timelines.



✨ Features

- 🔐 Login/Logout  Authentication via Firebase (login/signup/logout)
- 👤 User Profiles with personal post history
- 📷 Image Uploads via Cloud Storage (JPG/PNG only)
- 📝 Post Captions and optional comments (max 200 characters)
- 👥 Following System — Follow/unfollow users
- 📰 Timeline combining user and followed users' posts
- 💬 Comment System (first 5 shown, rest expandable)
- 🔍 Search by profile name (starts with...)
- ✅ Firestore Composite Indexes for Post queries
- ☁️ Built on FastAPI, Firebase Auth, Firestore, and Cloud Storage


 Tech Stack

- Backend: Python with FastAPI
- Frontend: HTML, CSS, JavaScript
- Database: Firestore (NoSQL, Document-based)
- Image Hosting: Firebase Cloud Storage
- Authentication: Firebase Authentication

 Project Structure

├── main.py - FastAPI app with routing
├── static/ - JS, CSS, and image assets
├── templates/  - HTML files
├── requirements.txt - Python dependencies
└── .gitignore - Excludes secrets and cached files

 What I Learned

- How to integrate Cloud Firestore with FastAPI
- Handling cloud-based image uploads via Cloud Storage
- Using Firestore indexes to sort user posts
- Creating a clean, intuitive social media-style UI
- Managing Git safely (e.g., excluding sensitive files)

---

Run Locally

1. Install dependencies:

bash
pip install -r requirements.txt
