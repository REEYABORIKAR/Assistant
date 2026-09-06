# REFYNE Frontend

This is the React frontend for the REFYNE enterprise AI workflow platform.

## Getting Started

1.  Install dependencies:
    ```bash
    npm install
    ```

2.  Start the development server:
    ```bash
    npm start
    ```

3.  The app will run on [http://localhost:3000](http://localhost:3000).

## Environment Variables

Create a `.env` file in the frontend directory to configure the backend API URL:

```
REACT_APP_API_URL=http://localhost:8000
```

## Available Features

-   Authentication (Login/Register)
-   Dashboard with metrics
-   Projects, Requirements, Workflows, Documents modules
-   Tenant isolation (enforced by backend middleware)
-   Responsive design based on UI mockups in `/docs/ui/`

## Project Structure

-   `src/` - Source code
-   `src/components/` - Reusable UI components
-   `src/contexts/` - React contexts (Auth, Tenant)
-   `src/pages/` - Page components for each route
-   `src/services/` - API service and utilities
-   `src/styles/` - CSS files (if any)

## Notes

-   The frontend is designed to work with the REFYNE backend API.
-   Ensure the backend is running and accessible at the URL specified in `.env`.
-   The backend tenant isolation middleware ensures users can only access resources belonging to their tenant.