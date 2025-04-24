const firebaseConfig = {
  apiKey: "AIzaSyCtrT-uXPnvYYeE88C6sOPL3diA4LNzg1c",
  authDomain: "my-project-yvonne-9ff25.firebaseapp.com",
  projectId: "my-project-yvonne-9ff25",
  storageBucket: "my-project-yvonne-9ff25.firebasestorage.app",
  messagingSenderId: "569288049886",
  appId: "1:569288049886:web:77376ba2f7faf881116e4f"
};

firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();


function login() {
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  if (!email || !password) {
    alert("Please enter both email and password.");
    return;
  }

  auth.signInWithEmailAndPassword(email, password)
    .then((userCredential) => {
      return userCredential.user.getIdToken().then((idToken) => {
        document.cookie = `token=${idToken}; path=/; max-age=3600; SameSite=Lax`;
        console.log("✅ Login successful. Token stored.");
        window.location.href = "/dashboard";
      });
    })
    .catch((error) => {
      console.error("❌ Login failed:", error.message);
      alert("Login failed: " + error.message);
    });
}


function signup() {
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  if (!email || !password) {
    alert("Please enter both email and password.");
    return;
  }

  console.log("📩 Attempting signup for:", email);

  auth.createUserWithEmailAndPassword(email, password)
    .then((userCredential) => {
      console.log("✅ Firebase user created:", userCredential.user.email);

      return userCredential.user.getIdToken().then(async (idToken) => {
        document.cookie = `token=${idToken}; path=/; max-age=3600; SameSite=Lax`;
        console.log("🔐 Token received:", idToken.slice(0, 20) + "...");

        const res = await fetch("/save_user", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${idToken}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ email: email })
        });

        console.log("📤 /save_user response:", res.status);

        if (res.ok) {
          alert("Signup successful! You can now log in.");
          window.location.href = "/dashboard";
        } else {
          const err = await res.json();
          console.error("❌ Backend rejected signup:", err);
          alert("Failed to save user: " + err.error);
        }
      });
    })
    .catch((error) => {
      console.error("❌ Firebase signup error:", error.message);
      alert("Signup failed: " + error.message);
    });
}


function logout() {
  auth.signOut().then(() => {
    document.cookie = "token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC";
    window.location.reload();
  });
}


auth.onAuthStateChanged((user) => {
  if (user) {
    console.log("✅ User is logged in:", user.email);
    const emailSpan = document.getElementById("user-email");
    if (emailSpan) emailSpan.innerText = user.email;

    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) logoutBtn.style.display = "block";
  } else {
    console.log("❌ User is logged out.");
    const emailSpan = document.getElementById("user-email");
    if (emailSpan) emailSpan.innerText = "Guest";

    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) logoutBtn.style.display = "none";
  }
});


document.addEventListener("DOMContentLoaded", () => {
  const loginBtn = document.getElementById("login-btn");
  const signupBtn = document.getElementById("signup-btn");

  if (loginBtn) {
    loginBtn.addEventListener("click", (e) => {
      e.preventDefault();
      login();
    });
  }

  if (signupBtn) {
    signupBtn.addEventListener("click", (e) => {
      e.preventDefault();
      signup();
    });
  }
});
