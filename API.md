# API Documentation

This document provides the authentication endpoints for logging in and logging out of the GateKeeper API.

## Base URL
```
http://localhost:8001/api/
```

## Authentication Endpoints

### 1. Login

**Endpoint:**
```
POST /api/login/
```

**Description:**
Obtain JWT tokens (access and refresh) for authentication. Accepts either username or email as the login identifier.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
    "username": "string",  // required - can be username or email
    "password": "string"   // required
}
```

**Success Response:**
```json
{
    "success": true,
    "access": "string",  // JWT access token
    "refresh": "string"  // JWT refresh token
}
```

**Error Responses:**

**400 Bad Request - Missing required fields**
```json
{
    "username": ["This field is required."],
    "password": ["This field is required."]
}
```

**401 Unauthorized - Invalid credentials or inactive/deleted account**
```json
{
    "detail": "No active account found with the given credentials"
}
```

---

### 2. Logout

**Endpoint:**
```
POST /api/logout/
```

**Description:**  
Logs out a user by blacklisting the refresh token. Optionally blacklists the access token if provided in the Authorization header.

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <access_token> (Optional)
```

**Request Body:**
```json
{
    "refresh": "string"  // required, JWT refresh token
}
```

**Success Response:**
```json
{
    "success": "Logged out successfully"
}
```

**Error Responses:**

**400 Bad Request - Missing token**
```json
{
    "error": "Refresh token is required"
}
```

**400 Bad Request - Invalid or expired token**
```json
{
    "error": "Invalid or expired token"
}
```

---

### 3. Token Refresh

**Endpoint:**
```
POST /api/token/refresh/
```

**Description:**
Obtain a new access token by providing a valid refresh token.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
    "refresh": "string"  // required, JWT refresh token
}
```

**Success Response:**
```json
{
    "access": "string"  // New JWT access token
}
```

**Error Responses:**

**400 Bad Request - Missing or incorrect refresh token**
```json
{
    "refresh": ["This field is required."]
}
```

**401 Unauthorized - Invalid or expired refresh token**
```json
{
    "detail": "Token is invalid or expired",
    "code": "token_not_valid"
}
```

---

### 4. Token Validation

**Endpoint:**
```
POST /api/validate_token/
```

**Description:**
Validate an access or refresh token to check if it is still valid and obtain the remaining time until expiration.

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
    "token": "string",      // required, JWT token to validate
    "token_type": "string"  // optional, "access" (default) or "refresh"
}
```

**Success Response:**
```json
{
    "success": true,
    "remaining_time_in_seconds": 1234  // Time left before the token expires
}
```

**Error Responses:**

**400 Bad Request - Missing token**
```json
{
    "error": "Token is required"
}
```

**400 Bad Request - Invalid token or incorrect token type**
```json
{
    "error": "Invalid access token"
}
```

**400 Bad Request - Expired token**
```json
{
    "error": "Access token has expired"
}
```

---

### 5. Get Current User (Me)

**Endpoint:**
```
GET /api/me/
```

**Description:**
Returns the authenticated user's profile and service permissions.

**Headers:**
```
Authorization: Bearer <access_token> (Required)
```

**Success Response:**
```json
{
    "user": {
        "uuid": "string",
        "username": "string",
        "email": "string",
        "first_name": "string",
        "last_name": "string",
        "groups": ["group1", "group2"]
    },
    "services": [
        {
            "code": "service_code",
            "name": "Service Name",
            "actions": ["view", "add", "edit", "delete"]
        }
    ]
}
```

**Error Responses:**

**401 Unauthorized - Missing or invalid token**
```json
{
    "detail": "Authentication credentials were not provided."
}
```

---

### 6. Who Am I

**Endpoint:**
```
GET /api/whoami/
```

**Description:**
Simple endpoint to check authentication status and get the current username.

**Headers:**
```
Authorization: Bearer <access_token> (Required)
```

**Success Response:**
```json
{
    "user": "username"
}
```

---

## Service Registry Endpoints

### 7. Register a Service

**Endpoint:**
```
POST /api/register_service/
```

**Description:**  
Register a new service endpoint or update an existing service with the provided data.
If a service with the same base url, service name, and endpoint exists:
- The service is updated with new methods, params, and comments.
- Existing methods are merged with the new ones provided.
- Existing params and comments are replaced with the new values.

If no matching service is found, a new service is created.

To remove method(s), use the Delete Service API.

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <access_token> (Required)
```

**Request Body:**
```json
{
    "base_url": "string",     // Required, base URL of the service (e.g., "http://service_name:8000/")
    "service_name": "string", // Required, name of the service (alphanumeric and underscores only)
    "endpoint": "string",     // Required, endpoint path (must NOT start with / and must NOT end with /)
    "methods": ["string"],    // Optional, list of HTTP methods (default: ["GET", "POST"])
    "params": "string",       // Optional, query parameter templates (e.g., "lat={}&lon={}")
    "comments": "string"      // Optional, comments for the service
}
```

**Validation Rules:**
- `base_url`: Must follow format `http://hostname:port/` or `https://hostname:port/`, max 100 chars
- `service_name`: Alphanumeric and underscores only, cannot start/end with underscore, max 30 chars
- `endpoint`: Must not start with `/` or `\`, max 100 chars

**Success Response:**

**201 Created - Service registered successfully**
```json
{
    "success": true,
    "message": "Service registered successfully",
    "service_id": 9
}
```

**200 OK - Existing service updated**
```json
{
    "success": true,
    "message": "Service updated successfully.",
    "service_id": 9
}
```

**Error Responses:**

**400 Bad Request - Missing required fields**
```json
{
    "error": "Missing required fields: endpoint"
}
```

**400 Bad Request - Methods not in the correct format**
```json
{
    "error": "Methods should be a list of strings."
}
```

**400 Bad Request - Base URL format invalid**
```json
{
    "error": "Base URL must follow the format 'http://baseurl:port/' or 'https://baseurl:port/'. The base URL name must only contain alphanumeric characters, dots (.), or underscores (_), and must start and end with an alphanumeric character. The port number must be 1-5 digits."
}
```

**400 Bad Request - Service Name invalid**
```json
{
    "error": "Service name must only contain alphanumeric characters and underscores. It cannot start or end with an underscore, and must be less than 30 characters long."
}
```

**400 Bad Request - Endpoint format invalid**
```json
{
    "error": "Endpoint must not start with a forward or backward slash."
}
```

**500 Internal Server Error**
```json
{
    "error": "A database error has occurred."
}
```

---

### 8. Service Directory

**Endpoint:**
```
GET /api/service_directory/
```

**Description:**
Retrieve a list of all registered active services. Optionally filter by service name, endpoint, or method.

**Headers:**
```
Content-Type: application/json
Authorization: Bearer <access_token> (Required)
```

**Query Parameters (Optional):**
| Parameter | Description |
|-----------|-------------|
| `service_name` | Partial or full match for the service name |
| `endpoint` | Partial or full match for the endpoint |
| `method` | HTTP method supported by the service |

**Success Response:**
```json
[
    {
        "base_url": "http://127.0.0.1:8003",
        "service_name": "weather_data",
        "endpoint": "get_temperature/{dd-mm-yyyy}/",
        "methods": ["POST", "DELETE", "GET"],
        "params": "",
        "comments": "",
        "service_url": "http://127.0.0.1:8001/api/proxy/weather_data/get_temperature/{dd-mm-yyyy}/"
    },
    {
        "base_url": "http://127.0.0.1:8002/",
        "service_name": "farm_calendar",
        "endpoint": "get_all_farms/{id}/",
        "methods": ["DELETE", "POST", "GET"],
        "params": "",
        "comments": "",
        "service_url": "http://127.0.0.1:8001/api/proxy/farm_calendar/get_all_farms/{id}/"
    }
]
```

**Error Responses:**

**500 Internal Server Error**
```json
{
    "error": "A database error has occurred."
}
```

---

### 9. Delete a Service

**Endpoint:**
```
DELETE /api/delete_service/
```

**Description:**  
Delete a service or a specific method associated with a service. You can:
- Delete the entire service by omitting the `method` parameter
- Remove a specific method by providing the `method` query parameter

**Headers:**
```
Authorization: Bearer <access_token> (Required)
```

**Query Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `base_url` | Yes | Base URL of the service |
| `service_name` | Yes | Name of the service |
| `endpoint` | Yes | Endpoint of the service |
| `method` | No | HTTP method to delete (e.g., "POST") |

**Success Responses:**

**200 OK - Entire service deleted**
```json
{
    "success": true,
    "message": "Base URL, service and endpoint deleted successfully."
}
```

**200 OK - Specific method removed**
```json
{
    "success": true,
    "message": "Method 'POST' removed from the service."
}
```

**Error Responses:**

**400 Bad Request - Missing required parameters**
```json
{
    "error": "Base URL, service name, and endpoint are required."
}
```

**400 Bad Request - Method not found**
```json
{
    "error": "Method 'POST' does not exist for this endpoint."
}
```

**404 Not Found - Service not found**
```json
{
    "error": "Service with this base URL, name, and endpoint does not exist or is already deleted."
}
```

**500 Internal Server Error**
```json
{
    "error": "A database error has occurred."
}
```

---

## Proxy Endpoint

### 10. Reverse Proxy

**Endpoint:**
```
GET|POST|PUT|PATCH|DELETE|OPTIONS /api/proxy/<service_name>/<endpoint_path>/
```

**Description:**
Routes authenticated requests to registered backend services. The GateKeeper validates the access token, checks service permissions, and forwards the request to the appropriate backend service.

**Headers:**
```
Authorization: Bearer <access_token> (Required)
Content-Type: application/json  // As required by the backend service
```

**URL Pattern:**
```
/api/proxy/{service_name}/{endpoint}/
```

**Example:**
```
GET /api/proxy/weather_data/get_temperature/01-01-2024/
```

**Success Response:**
Returns the response from the backend service (passthrough).

**Error Responses:**

**400 Bad Request - Invalid path**
```json
{
    "error": "Invalid path format."
}
```

**404 Not Found - Service not found**
```json
{
    "error": "No service can provide this resource."
}
```

**405 Method Not Allowed**
```json
{
    "error": "Method DELETE not allowed for this endpoint."
}
```

**401 Unauthorized - Missing or invalid token**
```json
{
    "detail": "Authentication credentials were not provided."
}
```

---

## Health Check Endpoint

### 11. Health Check

**Endpoint:**
```
GET /healthz
```

**Description:**
Health check endpoint for monitoring and container orchestration. Checks database connectivity.

**Success Response:**
```json
{
    "status": "ready"
}
```

**Error Response:**
```json
{
    "status": "error",
    "message": "Error description"
}
```

---

## Notes

- Ensure that authentication tokens are handled securely.
- The access token should be used in API requests requiring authentication.
- Refresh tokens should be stored securely and never exposed in frontend applications.
- Token expiration is configurable via environment variables.
- The `rjti` claim in access tokens links them to their parent refresh token for revocation purposes.

---
