import sqlite3  # 引入sqlite3庫，用於資料庫操作
from fastapi import FastAPI, Request, Form, Depends, HTTPException  # 引入FastAPI相關模組
from fastapi.responses import HTMLResponse, RedirectResponse  # 引入HTMLResponse與RedirectResponse，用於返回HTML頁面與重定向
from fastapi.templating import Jinja2Templates  # 引入Jinja2模板，用於渲染HTML模板
from fastapi.staticfiles import StaticFiles  # 引入靜態文件服務，用於提供靜態資源如CSS、JS
from itsdangerous import URLSafeSerializer  # 引入itsdangerous，用於加密Session
from pydantic import BaseModel, EmailStr, ValidationError  # 用於驗證郵件格式
from typing import Optional  # 引入Optional，用於指定返回類型可以是Optional

# ------------------ FastAPI App ------------------
app = FastAPI()  # 創建FastAPI應用

# 使用itsdangerous進行Session管理
SECRET_KEY = "your_secret_key"  # 設定一個密鑰，用於Session加密
serializer = URLSafeSerializer(SECRET_KEY)  # 創建一個序列化器實例，負責加密與解密Session

# 設定模板和靜態檔案目錄
templates = Jinja2Templates(directory="templates")  # 設定Jinja2模板所在的目錄
app.mount("/static", StaticFiles(directory="static"), name="static")  # 設定靜態文件路徑，這裡是/static目錄

# ------------------ 資料庫操作 ------------------

# 設定 SQLite3 資料庫連線
def get_db():
    conn = sqlite3.connect("blog.db")  # 連接SQLite3資料庫
    conn.row_factory = sqlite3.Row  # 使查詢結果以字典形式返回，便於根據列名訪問
    return conn  # 返回資料庫連線對象

# 初始化資料庫，建立必要的資料表
def init_db():
    conn = get_db()  # 獲取資料庫連線
    cursor = conn.cursor()  # 創建一個游標對象，用於執行SQL查詢
    # 創建用戶表格
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            email TEXT NOT NULL
        );
    """)
    # 創建文章表格
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL
        );
    """)
    conn.commit()  # 提交改動
    conn.close()  # 關閉資料庫連線

# ------------------ Session管理 ------------------

# 從請求中取得當前用戶資料
def get_current_user(request: Request) -> Optional[dict]:
    session_token = request.cookies.get("session_token")  # 獲取請求中的session_token
    if not session_token:  # 如果session_token不存在
        return None  # 返回None表示未登入
    try:
        user_data = serializer.loads(session_token)  # 解密session_token
        return user_data  # 返回解密後的用戶資料
    except Exception:  # 解密失敗時，處理異常
        return None  # 返回None，表示Session失效

# 設定Session
def set_session(response, user_data):
    session_token = serializer.dumps(user_data)  # 將用戶資料加密生成session_token
    response.set_cookie(key="session_token", value=session_token)  # 設置session_token到cookies中

# 清除Session
def clear_session(response):
    response.delete_cookie(key="session_token")  # 從cookies中刪除session_token，表示登出

# ------------------ 路由處理 ------------------

# 首頁 - 顯示所有文章
@app.get("/", response_class=HTMLResponse)
def list_posts(request: Request):
    user = get_current_user(request)  # 取得當前用戶資料
    conn = get_db()  # 獲取資料庫連線
    cursor = conn.cursor()  # 創建游標對象
    title = "歡迎來到 test post"
    cursor.execute("SELECT id, username, title, body FROM posts")  # 查詢所有文章
    posts = cursor.fetchall()  # 取得所有文章資料
    conn.close()  # 關閉資料庫連線
    return templates.TemplateResponse("/post/list.html", {"request": request, "user": user, "posts": posts,"title": title})  # 渲染列表頁面，並傳遞文章資料和當前用戶資料

# 註冊頁面
@app.get("/signup", response_class=HTMLResponse)
def signup_ui(request: Request):
    return templates.TemplateResponse("/login/signup.html", {"request": request,"title":"註冊"})  # 渲染註冊頁面

# 註冊處理
@app.post("/signup", response_class=HTMLResponse)
def signup( 
    request: Request,
    username: str = Form(...),  # 從表單中獲取username
    password: str = Form(...),  # 從表單中獲取password
    email: str = Form(...),  # 從表單中獲取email
):
    # 检查是否为空
    errors = {}
    if not username.strip():
        errors["username"] = "用户名不能為空"
    if not password.strip():
        errors["password"] = "密碼不能為空"
    if not email.strip():
        errors["email"] = "電子郵箱不能為空"

    # 使用 Pydantic 检查邮箱格式
    try:
        class EmailValidationModel(BaseModel):
            email: EmailStr
        EmailValidationModel(email=email)  # 验证邮箱
    except ValidationError:
        errors["email"] = "请输入有效的邮箱地址"

    # 检查用户名是否重复
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        errors["username"] = "该用户名已存在"
        return templates.TemplateResponse(
            "/login/signup.html",
            {"request": request, "errors": errors, "username": username, "email": email,"title":"註冊"},
        )
    
    # 如果有错误，返回到注册页面
    if errors:
        return templates.TemplateResponse(
            "/login/signup.html",
            {"request": request, "errors": errors, "username": username, "email": email,"title":"註冊"},
        )


    # 插入新用户
    cursor.execute(
        "INSERT INTO users (username, password, email) VALUES (?, ?, ?)",
        (username.strip(), password.strip(), email.strip()),
    )
    conn.commit()
    conn.close()

    # 注册成功后跳转到登录页面
    return RedirectResponse(url="/login", status_code=302)

# 登入頁面
@app.get("/login", response_class=HTMLResponse)
def login_ui(request: Request):
    return templates.TemplateResponse("/login/login.html", {"request": request,"title":"登入"})  # 渲染登入頁面

# 登入處理
@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),  # 從表單中獲取username
    password: str = Form(...),  # 從表單中獲取password
):
    conn = get_db()  # 獲取資料庫連線
    cursor = conn.cursor()  # 創建游標對象
    cursor.execute("SELECT id, username FROM users WHERE username = ? AND password = ?", (username, password))  # 查詢用戶名和密碼是否正確
    user = cursor.fetchone()  # 獲取查詢結果
    conn.close()  # 關閉資料庫連線
    if not user:  # 如果用戶名或密碼錯誤
        raise HTTPException(status_code=400, detail="Invalid credentials")  # 返回錯誤信息
    response = RedirectResponse(url="/", status_code=302)  # 登入成功，重定向到首頁
    set_session(response, {"id": user["id"], "username": user["username"]})  # 設置session，保存用戶登入狀態
    return response

# 登出
@app.get("/logout")
def logout(request: Request):
    response = RedirectResponse(url="/", status_code=302)  # 重定向到首頁
    clear_session(response)  # 清除Session，登出
    return response

# 新增文章頁面
@app.get("/post/new", response_class=HTMLResponse)
def new_post_ui(request: Request):
    user = get_current_user(request)  # 確認用戶是否登入
    if not user:
        return RedirectResponse(url="/?error=請先登錄")  # 传递错误信息给登录页面
    return templates.TemplateResponse("/post/new_post.html", {"request": request})  # 渲染新文章頁面

# 創建新文章
@app.post("/post")
def create_post(
    request: Request,
    title: str = Form(...),  # 從表單中獲取文章標題
    body: str = Form(...),  # 從表單中獲取文章內容
):
    user = get_current_user(request)  # 確認用戶是否登入
    if not user:
        return RedirectResponse(url="/?error=請先登錄")  # 传递错误信息给登录页面
    conn = get_db()  
    cursor = conn.cursor() 
    cursor.execute(
        "INSERT INTO posts (username, title, body) VALUES (?, ?, ?)",  # 插入新文章資料
        (user["username"], title, body),
    )
    conn.commit()  
    conn.close()  
    return RedirectResponse(url="/", status_code=302)  # 文章創建成功，重定向到首頁

# 查看單篇文章
@app.get("/post/{post_id}", response_class=HTMLResponse)
def view_post(request: Request, post_id: int):
    conn = get_db() 
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, title, body FROM posts WHERE id = ?", (post_id,))  # 查詢指定ID的文章
    post = cursor.fetchone()  # 獲取單篇文章資料
    conn.close()  
    if not post:  # 如果文章不存在
        raise HTTPException(status_code=404, detail="Post not found")  # 返回404錯誤
    return templates.TemplateResponse("/post/show_post.html", {"request": request, "post": post})  # 渲染文章頁面

# 初始化資料庫，建立必要的資料表
init_db()
