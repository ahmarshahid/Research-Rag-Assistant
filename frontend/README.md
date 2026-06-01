# AI Research Assistant - Frontend

Modern React/Next.js frontend for the AI Research Assistant RAG system.

## 🚀 Features

- **User Authentication**: Register, login, and logout with JWT tokens
- **Document Upload**: Upload PDF files for processing
- **Multi-turn Chat**: Have conversations with documents with context awareness
- **Document Search**: Full-text and semantic search across documents
- **Responsive Design**: Mobile-friendly UI built with Tailwind CSS
- **TypeScript**: Full type safety throughout the application
- **Real-time Updates**: Live chat interface with instant responses

## 📦 Tech Stack

- **Framework**: Next.js 14
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: Zustand
- **HTTP Client**: Axios
- **Notifications**: React Hot Toast
- **Icons**: React Icons

## 🛠️ Installation

### Prerequisites

- Node.js 18+ 
- npm or yarn
- Backend API running on `http://localhost:8000`

### Setup

1. **Install dependencies**:

```bash
cd frontend
npm install
```

2. **Configure environment**:

```bash
cp .env.local.example .env.local
```

Edit `.env.local` if needed (default backend URL is correct for local development).

3. **Start development server**:

```bash
npm run dev
```

Frontend will be available at `http://localhost:3000`

## 📁 Project Structure

```
frontend/
├── public/                 # Static assets
├── src/
│   ├── pages/             # Next.js pages/routes
│   │   ├── _app.tsx       # App wrapper
│   │   ├── auth/          # Authentication pages
│   │   │   ├── login.tsx
│   │   │   └── register.tsx
│   │   ├── dashboard.tsx  # Main dashboard
│   │   ├── chat.tsx       # Chat interface
│   │   └── search.tsx     # Search interface
│   ├── components/        # Reusable components
│   ├── lib/               # Utilities and stores
│   │   ├── api.ts        # API client
│   │   └── auth-store.ts # Auth state store
│   └── styles/            # CSS files
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js
```

## 🔐 Authentication

### User Flow

1. **Register**: Create account at `/auth/register`
   - Email, username, password
   - Password must contain uppercase, digit, special character

2. **Login**: Sign in at `/auth/login`
   - Email and password
   - Get JWT tokens (access + refresh)

3. **Protected Routes**: Automatically redirects to login if not authenticated

4. **Logout**: Click logout button to revoke tokens

### Token Management

- **Access Token**: 15-minute expiration
- **Refresh Token**: 7-day expiration
- Automatic token refresh on API calls
- Tokens stored in localStorage
- Logout blacklists tokens

## 📖 Pages

### 1. Login Page (`/auth/login`)

Login with email and password.

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"SecurePass123!"}'
```

### 2. Register Page (`/auth/register`)

Create new account.

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","username":"john","password":"SecurePass123!"}'
```

### 3. Dashboard (`/dashboard`)

Main hub with:
- Document upload
- Quick navigation to chat and search
- List of uploaded documents
- Document status tracking

### 4. Chat (`/chat`)

Multi-turn conversation interface:
- Create new chat sessions
- Chat with selected document
- View conversation history
- See citations for responses
- List previous sessions

### 5. Search (`/search`)

Find information in documents:
- Select document
- Enter search query
- View results with similarity scores
- Navigate to specific pages

## 🔗 API Integration

All API calls go through `/src/lib/api.ts`:

```typescript
// Authentication
apiClient.register(email, username, password)
apiClient.login(email, password)
apiClient.logout()
apiClient.getCurrentUser()

// Documents
apiClient.uploadDocument(file)
apiClient.listDocuments()
apiClient.getDocument(documentId)
apiClient.deleteDocument(documentId)

// Search
apiClient.searchDocuments(documentId, query, topK)

// RAG
apiClient.askQuestion(documentId, query, model, topK)
apiClient.askQuestionStream(documentId, query, model)

// Chat
apiClient.createChatSession(documentIds, title)
apiClient.listChatSessions()
apiClient.getChatSession(sessionId)
apiClient.getChatHistory(sessionId)
apiClient.sendChatMessage(sessionId, content)
apiClient.deleteChatSession(sessionId)
```

## 🎨 Styling

Built with Tailwind CSS for consistency and maintainability.

### Color Scheme

- **Primary**: Blue (#0ea5e9)
- **Background**: Light slate (#f8fafc)
- **Border**: Slate (#e2e8f0)

### Responsive Design

- Mobile-first approach
- Breakpoints: `sm`, `md`, `lg`, `xl`, `2xl`
- Flexible layouts using grid and flexbox

## 🚀 Building for Production

### Build

```bash
npm run build
```

### Start Production Server

```bash
npm start
```

### Environment Variables for Production

```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

## 🧪 Development Tips

### Type Safety

All TypeScript types are automatically inferred from API responses:

```typescript
interface DocumentResponse {
  id: string
  filename: string
  page_count: number
  // ... other fields
}
```

### State Management

Using Zustand for simple, efficient state:

```typescript
const { user, login, logout, isLoading } = useAuthStore()
```

### Error Handling

All errors automatically show toast notifications:

```typescript
toast.error('Something went wrong')
toast.success('Operation successful')
```

## 📱 Browser Support

- Chrome/Chromium (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## 🤝 Contributing

1. Create feature branch: `git checkout -b feature/name`
2. Make changes and test
3. Commit: `git commit -m "Add feature"`
4. Push: `git push origin feature/name`
5. Open PR

## 📄 License

MIT

## 🆘 Troubleshooting

### Frontend won't connect to backend

- Ensure backend is running on `http://localhost:8000`
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Look for CORS errors in browser console

### Login fails

- Check credentials in backend
- Ensure backend auth endpoints are working
- Check network tab in dev tools

### Build errors

- Delete `node_modules` and `.next`
- Run `npm install` again
- Clear Next.js cache: `npm run build`

## 📚 Additional Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [Tailwind CSS](https://tailwindcss.com)
- [Zustand](https://github.com/pmndrs/zustand)
- [Axios](https://axios-http.com)

---

**Frontend Status**: ✅ Production Ready

Fully implemented React/Next.js frontend with authentication, document upload, chat, and search interfaces.
