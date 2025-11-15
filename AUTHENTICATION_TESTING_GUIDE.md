# CDSA Authentication Testing Guide

## ✅ What We've Implemented

### Backend (Already Complete)
- ✅ JWT-based authentication with access and refresh tokens
- ✅ User registration endpoint: `POST /api/v1/auth/register`
- ✅ Login endpoint: `POST /api/v1/auth/login`
- ✅ Protected endpoints requiring authentication
- ✅ Test user created in database

### Frontend (Just Completed)
- ✅ LoginView component with login/registration forms
- ✅ authService with JWT token management
- ✅ Automatic token refresh on 401 errors
- ✅ Authentication state management in App.tsx
- ✅ Conditional rendering (LoginView vs main app)
- ✅ Logout button in Sidebar
- ✅ Protected API calls using `fetchWithAuth`

---

## 🔑 Test Credentials

A test user has been created for you:

```
Username: admin
Password: admin123
Email: admin@cdsa.local
Role: Manager
```

The Manager role has permissions to upload documents.

---

## 🧪 Testing Steps

### 1. Access the Application

1. Open your browser to: **http://localhost:3000**
2. You should see the **Login View** with:
   - Username and Password fields
   - "Login" button
   - "Don't have an account? Register" link

### 2. Test Login Flow

#### Option A: Login with Test User
1. Enter credentials:
   - Username: `admin`
   - Password: `admin123`
2. Click "Login"
3. Upon success:
   - You should be redirected to the main CDSA app
   - The Sidebar should show your user info (Admin User / Manager)
   - All navigation options should be visible

#### Option B: Test Registration
1. Click "Don't have an account? Register"
2. Fill in the registration form:
   - Username: (choose a unique username)
   - Email: (valid email format)
   - Full Name: (your name)
   - Password: (at least 8 characters)
3. Click "Register"
4. Upon success:
   - You should be automatically logged in
   - Redirected to the main app

### 3. Test Document Upload (Protected Route)

This verifies that authentication is working for protected API endpoints.

1. Once logged in, navigate to **Documents** view (sidebar)
2. Click the **"Upload Document"** button
3. Fill in the upload form:
   - Select a file (PDF, DOCX, or TXT)
   - Enter title (optional)
   - Select classification: Confidential/Internal/Public
   - Select type: Policy/Guide/Report
4. Click "Upload"
5. **Expected Result**: 
   - ✅ Document uploads successfully (no 403 Forbidden error)
   - ✅ Document appears in the documents list
   - ✅ Success message displayed

### 4. Test Logout

1. In the Sidebar, locate the session control section
2. Click the **"Logout"** button (red button next to "Switch User")
3. **Expected Result**:
   - ✅ You're redirected back to the Login View
   - ✅ All tokens are cleared from localStorage
   - ✅ Can no longer access protected routes

### 5. Test Auto Token Refresh

This happens automatically in the background:

1. Log in successfully
2. Use the app normally
3. After some time (when access token expires), make an API call
4. **Expected Result**:
   - ✅ The system automatically refreshes the token
   - ✅ Your request proceeds without interruption
   - ✅ No visible error or login prompt

---

## 🐛 Troubleshooting

### Login Button Doesn't Respond
- Check browser console (F12) for errors
- Verify backend is running: http://localhost:8001/health
- Check Network tab to see if login request is sent

### 403 Forbidden on Upload
- Verify you're logged in (check localStorage for `cdsa_access_token`)
- Check that the user has Manager or Admin role
- Open browser console and look for authentication errors

### "Loading..." Screen Forever
- Check backend is running and accessible
- Open browser console for errors
- Try clearing localStorage and refreshing

### Backend Connection Issues
- Verify Docker services are running:
  ```bash
  cd backend && docker-compose ps
  ```
- Verify backend server is running:
  ```bash
  # Should see uvicorn server logs
  ```

---

## 📊 Verification Checklist

Use this checklist to verify everything works:

- [ ] Navigate to http://localhost:3000
- [ ] See Login View (not main app)
- [ ] Login with admin/admin123 works
- [ ] Redirected to main app after login
- [ ] User info shows in Sidebar (Admin User / Manager)
- [ ] Navigate to Documents view
- [ ] Upload Document button is visible
- [ ] Can upload a document successfully (no 403 error)
- [ ] Document appears in documents list
- [ ] Logout button works
- [ ] Redirected back to Login View after logout
- [ ] Can login again successfully

---

## 🔄 Current Servers Running

Make sure these are active:

1. **Backend Server**: http://localhost:8001
   - Started with: `cd backend && source .venv/bin/activate && python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload`
   
2. **Frontend Dev Server**: http://localhost:3000
   - Started with: `npm run dev`

3. **Docker Services** (PostgreSQL, Redis):
   - Started with: `cd backend && docker-compose up -d`

---

## 📝 Important Files Modified

### Frontend:
- `App.tsx` - Added authentication state, conditional rendering, handlers
- `components/LoginView.tsx` - New login/registration component
- `components/Sidebar.tsx` - Added logout button
- `services/authService.ts` - New authentication service with JWT management
- `vite.config.ts` - Added proxy configuration

### Backend:
- `backend/scripts/create_test_user.py` - Script to create test users

---

## 🎯 Next Steps After Testing

Once you've verified authentication works:

1. **Add More Users**: Run the create_test_user.py script again with different credentials
2. **Test Other Protected Routes**: Try other features that require authentication
3. **Test Role-Based Access**: Create users with different roles (Viewer, Analyst, Manager, Admin)
4. **Production Setup**: Configure proper secrets and security settings before deployment

---

## 🆘 Need Help?

If you encounter issues:

1. Check browser console (F12 → Console tab)
2. Check Network tab to see API request/response
3. Check backend logs in the terminal
4. Verify all environment variables are set correctly in `backend/.env`

---

## 🎉 Success Criteria

Your authentication system is working correctly when:

✅ Login prevents access to the app without credentials  
✅ Users can register new accounts  
✅ Document upload works without 403 errors  
✅ Token refresh happens automatically  
✅ Logout clears session and returns to login  
✅ Re-login works after logout