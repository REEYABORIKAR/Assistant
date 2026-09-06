# Frontend Startup Instructions

## Prerequisites
- Node.js (v14+ recommended)
- npm (comes with Node.js)
- Backend server running (see backend instructions)

## Installation
Due to temporary sandbox restrictions in this environment, you need to install dependencies manually:

```bash
cd frontend
npm install
```

## Starting the Development Server
After installation completes:

```bash
npm start
```

The frontend will be available at http://localhost:3000

## Backend Connection
Ensure the backend is running and accessible at http://localhost:8000
If your backend runs on a different port or host, update the REACT_APP_API_URL in a .env file:

```
REACT_APP_API_URL=http://your-backend-host:port
```

## Troubleshooting
- If you see "'react-scripts' is not recognized", run `npm install` first
- Ensure backend CORS is configured to allow http://localhost:3000
- Check browser console for any API connection errors
- Verify you're logged in (check localStorage for token)

## Available Features
- Authentication (Login/Register)
- Tenant-aware dashboard showing current tenant
- Projects, Requirements, Workflows, Documents modules (basic list views)
- Placeholder pages for Chat, Integrations, Approvals, Admin (ready for enhancement)
- Automatic JWT token handling in API requests
- Proper error handling for 401/403 responses

## Next Steps
1. Install dependencies with `npm install`
2. Start backend server
3. Start frontend with `npm start`
4. Register/login to test authentication
5. Verify tenant isolation by attempting to access resources from different tenants