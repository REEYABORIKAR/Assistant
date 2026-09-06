# Frontend Implementation Plan

## Overview
Create a React frontend that consumes the REFYNE backend API, implementing all features shown in the UI mockups in `/docs/ui/` and described in the documentation.

## Pages to Implement (based on UI images)
1. Login (`login.png`)
2. Register (`register.png`)
3. Dashboard (`admin.png`, `approval.png`, `documents.png`, `integrations.png`, `project.png`, `review.png`, `workflow.png`, `workflow-running.png`, `chat.png`, `brd-preview.png`, `srs-preview.png`, `document-generator.png`, `rtm.png`)
4. Specific modules: Projects, Requirements, Workflows, Documents, Chat, Integrations, Approvals, Admin

## Technical Stack
- React 18
- React Router v6
- Axios for HTTP requests
- Context API for auth/tenant state
- CSS Modules or Tailwind (choose one)

## Implementation Steps

### 1. Project Setup
```bash
cd frontend
npm install react react-dom react-router-dom axios
# Optionally: npm install tailwindcss postcss autoprefixer
```

### 2. Core Components
- `src/App.js` - Router setup
- `src/contexts/AuthContext.js` - JWT token, user info, tenant info
- `src/contexts/TenantContext.js` - Current tenant selection
- `src/services/api.js` - Axios instance with interceptors for auth
- `src/routes/` - Route components for each page
- `src/components/` - Reusable UI components (buttons, forms, modals, tables, charts)

### 3. Authentication Flow
- Login page: POST `/api/v1/auth/login`
- Register page: POST `/api/v1/auth/register`
- Store JWT in localStorage or cookie
- Refresh token handling via `/api/v1/auth/refresh`
- Logout: clear storage, call `/api/v1/auth/logout`

### 4. Tenant Awareness
- After login, fetch `/api/v1/tenants/current` to get user's tenant
- All API calls include tenant context implicitly via middleware
- UI displays current tenant name (from mockups)

### 5. Module Implementations (mapping to UI images)

#### Dashboard (`admin.png`)
- Overview metrics panel
- Quick navigation to modules

#### Projects (`project.png`)
- List projects with create/edit/delete
- Project details view

#### Requirements (`brd-preview.png`, `srs-preview.png`, `rtm.png`)
- Requirements tree/list
- BRD/SRS preview
- RTM (Requirements Traceability Matrix) view

#### Workflows (`workflow.png`, `workflow-running.png`)
- Workflow designer/list
- Running workflows monitor

#### Documents (`documents.png`, `document-generator.png`)
- Document repository
- Document generation wizard

#### Chat (`chat.png`)
- Real-time chat interface (if WebSocket available, otherwise polling)

#### Integrations (`integrations.png`)
- Third-party integration configuration

#### Approvals (`approval.png`)
- Approval workflow UI

#### Admin (`admin.png`)
- User/role management
- Tenant settings
- System configuration

### 6. API Integration Details
- Use axios instance with base URL from environment
- Request interceptor: add Authorization header from auth context
- Response interceptor: handle 401 (redirect to login), 403 (show access denied)
- Error handling: display user-friendly messages

### 7. State Management
- AuthContext: token, user, login/logout/refresh
- TenantContext: current tenant, tenant switching if multi-tenant allowed
- Module-specific states (useReducer or Zustand if needed)

### 8. Styling Approach
- Use CSS modules for component-scoped styling
- Extract design tokens from UI mockups (colors, spacing, typography)
- Responsive layout matching mockups

### 9. Testing
- Unit tests for services and context
- E2E tests with Cypress for critical paths (login, project CRUD)

### 10. Build & Deployment
- Create production build: `npm run build`
- Serve via static file server or integrate with backend for serving

## Acceptance Criteria
- All UI mockups have functional counterparts
- Authentication works with backend
- Tenant isolation respected (users only see their tenant's data)
- Responsive design matching mockups
- No console errors in production build
- API calls properly formatted and handled

## Dependencies from Backend
- CORS configured to allow frontend origin
- Auth endpoints returning JWT with proper expiration
- Tenant middleware correctly isolating data
- Health endpoint `/health` for connectivity check

## Next Steps
1. Begin with AuthContext and login/register pages
2. Implement dashboard with mock data
3. Connect to real API for tenant info
4. Implement each module iteratively
5. Add error handling and loading states
6. Polish UI to match mockups
7. Write tests
8. Prepare for production build