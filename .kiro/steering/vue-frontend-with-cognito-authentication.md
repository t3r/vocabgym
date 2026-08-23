# Vue Frontend with Cognito Authentication

## Project Context

This document describes the frontend implementation for VocabTrainer, a web-based French vocabulary training application for 9th grade German Gymnasium students. The application allows students to scan workbook pages, extract vocabulary through AI, and practice with typing-based exercises.

## Technology Stack

- **Framework**: Vue 3 with Composition API
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: Pinia
- **Routing**: Vue Router
- **HTTP Client**: Axios
- **Authentication**: AWS Cognito (OAuth2 flow with hosted UI)
- **Charts**: Chart.js or similar for progress visualization
- **Deployment**: AWS S3 + CloudFront CDN

## Architecture Overview

The frontend is a Single Page Application (SPA) that communicates with a serverless backend via REST API. Authentication is handled entirely by AWS Cognito using the OAuth2 authorization code flow with PKCE. The Cognito hosted UI manages login, registration, and password reset flows.

### High-Level Flow

1. User accesses application via CloudFront URL
2. Unauthenticated users are redirected to Cognito hosted UI
3. After successful authentication, Cognito redirects back with authorization code
4. Frontend exchanges code for JWT tokens (handled by Cognito SDK)
5. All API requests include JWT token in Authorization header
6. API Gateway validates token against Cognito before invoking Lambda functions

## Project Structure

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── assets/
│   │   └── styles/
│   │       └── main.css
│   ├── components/
│   │   ├── common/
│   │   │   ├── AppHeader.vue
│   │   │   ├── LoadingSpinner.vue
│   │   │   └── ErrorMessage.vue
│   │   ├── vocab/
│   │   │   ├── VocabCard.vue
│   │   │   ├── VocabList.vue
│   │   │   └── VocabTable.vue
│   │   ├── upload/
│   │   │   ├── ImageUploader.vue
│   │   │   └── UploadProgress.vue
│   │   ├── practice/
│   │   │   ├── PracticeCard.vue
│   │   │   ├── AnswerInput.vue
│   │   │   └── SessionSummary.vue
│   │   └── progress/
│   │       ├── ProgressChart.vue
│   │       └── StatsCard.vue
│   ├── views/
│   │   ├── LandingView.vue
│   │   ├── DashboardView.vue
│   │   ├── UploadView.vue
│   │   ├── ReviewView.vue
│   │   ├── PracticeView.vue
│   │   ├── ProgressView.vue
│   │   └── VocabDetailView.vue
│   ├── router/
│   │   └── index.js
│   ├── stores/
│   │   ├── auth.js
│   │   ├── vocab.js
│   │   ├── practice.js
│   │   └── progress.js
│   ├── services/
│   │   ├── api.js
│   │   ├── auth.js
│   │   └── cognito.js
│   ├── utils/
│   │   ├── validators.js
│   │   └── formatters.js
│   ├── App.vue
│   └── main.js
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## AWS Cognito Configuration

### User Pool Settings

- **User Pool Name**: vocabtrainer-users
- **Sign-in Options**: Email
- **MFA**: Optional (recommended: OFF for students)
- **Password Policy**: 
  - Minimum length: 8 characters
  - Require uppercase, lowercase, numbers
  - No special characters required (student-friendly)
- **Email Verification**: Required
- **Hosted UI Domain**: vocabtrainer-auth-{env}.auth.{region}.amazoncognito.com

### App Client Configuration

- **App Client Type**: Public client
- **Authentication Flows**: 
  - ALLOW_USER_PASSWORD_AUTH
  - ALLOW_REFRESH_TOKEN_AUTH
- **OAuth 2.0 Settings**:
  - Allowed OAuth Flows: Authorization code grant with PKCE
  - Allowed OAuth Scopes: openid, email, profile
  - Callback URLs: 
    - Development: http://localhost:5173/callback
    - Production: https://{cloudfront-domain}/callback
  - Sign-out URLs:
    - Development: http://localhost:5173
    - Production: https://{cloudfront-domain}
- **Token Expiration**:
  - ID Token: 60 minutes
  - Access Token: 60 minutes
  - Refresh Token: 30 days

### Custom Attributes

- **preferred_language**: String (default: "de")
- **grade_level**: Number (default: 9)

## Environment Configuration

Create `.env` and `.env.production` files:

```
VITE_AWS_REGION=eu-central-1
VITE_COGNITO_USER_POOL_ID=eu-central-1_XXXXXXXXX
VITE_COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
VITE_COGNITO_DOMAIN=vocabtrainer-auth-prod.auth.eu-central-1.amazoncognito.com
VITE_API_BASE_URL=https://api.vocabtrainer.com
VITE_CALLBACK_URL=https://app.vocabtrainer.com/callback
VITE_LOGOUT_URL=https://app.vocabtrainer.com
```

## Authentication Implementation

### Cognito Service (src/services/cognito.js)

The Cognito service manages the OAuth2 flow using the amazon-cognito-identity-js SDK or AWS Amplify Auth.

**Key Responsibilities**:
- Generate PKCE code challenge/verifier
- Redirect to Cognito hosted UI for login
- Handle callback with authorization code
- Exchange authorization code for tokens
- Store tokens securely (localStorage with encryption consideration)
- Refresh tokens automatically
- Handle logout (clear tokens + Cognito sign-out)

**Methods**:
- `initiateLogin()`: Redirects to Cognito hosted UI
- `handleCallback(code)`: Exchanges code for tokens
- `refreshAccessToken()`: Gets new access token using refresh token
- `logout()`: Clears local tokens and redirects to Cognito logout
- `getCurrentUser()`: Returns decoded JWT user info
- `isAuthenticated()`: Checks token validity

### Auth Store (src/stores/auth.js)

Pinia store managing authentication state.

**State**:
```javascript
{
  user: null, // { sub, email, name, ... }
  accessToken: null,
  idToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: false,
  error: null
}
```

**Actions**:
- `login()`: Initiates OAuth flow
- `handleAuthCallback(code)`: Processes callback
- `logout()`: Clears auth state
- `refreshSession()`: Refreshes tokens
- `loadUserFromStorage()`: Restores session on page load
- `checkTokenExpiry()`: Validates token freshness

### Router Guards (src/router/index.js)

Implement navigation guards to protect routes:

```javascript
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  // Public routes
  if (to.meta.public) {
    return next()
  }
  
  // Auth callback route
  if (to.path === '/callback') {
    return next()
  }
  
  // Protected routes
  if (!authStore.isAuthenticated) {
    authStore.login() // Redirect to Cognito
  } else {
    next()
  }
})
```

## API Integration

### API Service (src/services/api.js)

Axios instance with interceptors for authentication and error handling.

**Configuration**:
- Base URL from environment variable
- Request interceptor: Attach JWT token to Authorization header
- Response interceptor: Handle 401 (refresh token), 403, network errors
- Automatic retry logic for token refresh

**Example Structure**:
```javascript
const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 30000
})

// Request interceptor
apiClient.interceptors.request.use((config) => {
  const token = authStore.accessToken
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Attempt token refresh
      await authStore.refreshSession()
      // Retry original request
      return apiClient.request(error.config)
    }
    return Promise.reject(error)
  }
)
```

**Exported Methods**:
- `get(url, config)`
- `post(url, data, config)`
- `put(url, data, config)`
- `delete(url, config)`

## Application Routes

### Route Configuration

| Path | Component | Auth Required | Description |
|------|-----------|--------------|-------------|
| `/` | LandingView | No | Landing page with login prompt |
| `/callback` | CallbackView | No | OAuth callback handler |
| `/dashboard` | DashboardView | Yes | Main dashboard with vocab sets |
| `/upload` | UploadView | Yes | Image upload interface |
| `/review/:vocabSetId` | ReviewView | Yes | Review extracted vocabulary |
| `/practice/:vocabSetId` | PracticeView | Yes | Practice session |
| `/progress` | ProgressView | Yes | Overall progress statistics |
| `/vocab/:vocabSetId` | VocabDetailView | Yes | View/edit vocabulary set |

### Route Metadata

Each route should include metadata:
```javascript
{
  path: '/dashboard',
  component: DashboardView,
  meta: {
    requiresAuth: true,
    title: 'Dashboard'
  }
}
```

## Key Views & Components

### LandingView.vue

**Purpose**: Entry point for unauthenticated users

**Features**:
- Hero section explaining the app
- "Get Started" button triggering Cognito login
- Brief feature overview (scan, review, practice)
- Visual mockups or screenshots
- Responsive design for mobile/tablet/desktop

**Behavior**:
- If user is already authenticated, redirect to /dashboard
- Otherwise, show marketing content

### DashboardView.vue

**Purpose**: Main hub showing all vocabulary sets

**Layout**:
- Header with user name, logout button
- "Upload New Workbook Page" prominent button
- Grid/list of vocabulary sets with:
  - Thumbnail of source image
  - Title (e.g., "Chapter 3: School")
  - Item count (e.g., "24 words")
  - Last practiced date
  - Quick action buttons: Practice, View, Delete
- Filter/sort options (by date, chapter, mastery)
- Quick stats widget: total words, mastery percentage, practice streak

**State Management**:
- Uses vocab store to fetch and display all vocab sets
- Real-time updates when new sets are added

### UploadView.vue

**Purpose**: Upload and process workbook images

**Components Used**:
- ImageUploader component (drag-and-drop zone)
- UploadProgress component (shows processing status)

**Flow**:
1. User drags image or clicks to browse
2. Image preview shown
3. "Process" button sends image to backend
4. Progress indicator during upload and extraction
5. On completion, redirect to ReviewView with vocabSetId

**Technical Details**:
- Accept JPG, PNG, HEIC formats
- Client-side validation (file size < 10MB, image dimensions)
- Request presigned S3 URL from backend
- Upload directly to S3 using presigned URL
- Trigger extraction Lambda via API
- Poll extraction status or use WebSocket for real-time updates

### ReviewView.vue

**Purpose**: Review and edit extracted vocabulary before approval

**Layout**:
- Left panel: Original workbook image
- Right panel: Editable table of extracted vocabulary
  - German column
  - French column
  - Delete row button
  - Add row button
- Metadata inputs: Title, Chapter, Page Number, Topic
- "Approve & Save" button (primary action)
- "Cancel" button

**Features**:
- Inline editing of German/French pairs
- Validation: no empty fields
- Highlight potential extraction errors (empty cells, unusual characters)
- Keyboard shortcuts: Tab to move between cells, Enter to add row

**State Management**:
- Fetch extraction results from API on mount
- Local state for editing before save
- On save, update vocab store and redirect to dashboard

### PracticeView.vue

**Purpose**: Interactive practice session

**Components Used**:
- PracticeCard (displays question)
- AnswerInput (text input with submit)
- SessionSummary (modal showing results)

**Session Flow**:
1. Load questions from selected vocab set
2. Randomize order or use sequential
3. For each question:
   - Display German word (or French, based on direction)
   - Show text input for answer
   - User types and submits (Enter key or button)
   - Immediate feedback: correct (green) or incorrect (red)
   - If incorrect, show correct answer
   - "Next" button to continue
4. After all questions, show SessionSummary modal:
   - Score: X/Y correct
   - Time taken
   - List of mistakes
   - "Practice Again" or "Back to Dashboard" buttons

**Technical Details**:
- Store session state locally (questions, current index, answers)
- Fuzzy matching for answers (strip accents, case-insensitive, trim whitespace)
- Submit results to backend on session completion
- Update progress statistics

**UI/UX**:
- Clean, minimal design to reduce distractions
- Large, clear fonts for readability
- Visual feedback animations (shake on wrong, checkmark on correct)
- Progress bar showing position in session
- Optional: show remaining question count

### ProgressView.vue

**Purpose**: Visualize learning progress

**Layout**:
- Overall statistics card:
  - Total vocabulary sets
  - Total words learned
  - Average mastery level
  - Practice streak (days)
- Charts:
  - Bar chart: mastery distribution (how many words at each mastery level)
  - Line chart: practice activity over time
  - Pie chart: vocabulary by chapter/topic
- Recent practice sessions table
- Words needing review (low mastery level)

**Components Used**:
- ProgressChart (Chart.js wrapper)
- StatsCard (reusable statistic display)

**Data Sources**:
- Fetch from /progress/overview API
- Aggregate data from practice sessions
- Calculate mastery levels based on correct/incorrect counts

## State Management (Pinia Stores)

### Auth Store (auth.js)

Already described above. Manages user authentication state and token lifecycle.

### Vocab Store (vocab.js)

**State**:
```javascript
{
  vocabSets: [], // Array of vocab set objects
  currentVocabSet: null, // Currently viewed/edited vocab set
  isLoading: false,
  error: null
}
```

**Actions**:
- `fetchVocabSets()`: Load all vocab sets for user
- `fetchVocabSet(id)`: Load specific vocab set with items
- `createVocabSet(data)`: Create new vocab set
- `updateVocabSet(id, data)`: Update vocab set
- `deleteVocabSet(id)`: Delete vocab set
- `uploadImage(file)`: Handle image upload flow
- `processImage(imageKey)`: Trigger extraction

**Getters**:
- `getVocabSetById(id)`: Find specific vocab set
- `sortedVocabSets`: Return vocab sets sorted by date
- `vocabSetsByChapter`: Group vocab sets by chapter

### Practice Store (practice.js)

**State**:
```javascript
{
  currentSession: null, // { questions, answers, startTime, vocabSetId }
  sessionHistory: [], // Array of completed sessions
  isLoading: false,
  error: null
}
```

**Actions**:
- `startSession(vocabSetId, options)`: Initialize practice session
- `submitAnswer(answer)`: Check answer and store result
- `nextQuestion()`: Move to next question
- `completeSession()`: Finalize and save session
- `fetchSessionHistory()`: Load past sessions

**Getters**:
- `currentQuestion`: Get current question object
- `sessionProgress`: Calculate percentage complete
- `sessionScore`: Calculate current score

### Progress Store (progress.js)

**State**:
```javascript
{
  overallStats: null, // { totalWords, masteryAverage, practiceStreak }
  vocabSetProgress: {}, // Map of vocabSetId -> progress data
  isLoading: false,
  error: null
}
```

**Actions**:
- `fetchOverallProgress()`: Load overall statistics
- `fetchVocabSetProgress(id)`: Load progress for specific vocab set
- `updateProgress(sessionResults)`: Update after practice session

**Getters**:
- `masteryDistribution`: Calculate mastery level distribution
- `recentActivity`: Get recent practice data for charts
- `wordsNeedingReview`: Filter words with low mastery

## Styling with Tailwind CSS

### Configuration (tailwind.config.js)

Extend default theme with custom colors, fonts, and utilities:

```javascript
module.exports = {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8'
        },
        success: '#10b981',
        error: '#ef4444',
        warning: '#f59e0b'
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif']
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms')
  ]
}
```

### Design System Guidelines

**Colors**:
- Primary: Blue (#3b82f6) for CTAs, links, active states
- Success: Green (#10b981) for correct answers, completion
- Error: Red (#ef4444) for incorrect answers, validation errors
- Neutral: Gray scale for text, backgrounds, borders

**Typography**:
- Headings: Bold, larger sizes (text-2xl to text-4xl)
- Body: Regular weight, comfortable reading size (text-base)
- Vocabulary words: Larger (text-xl), clear font

**Spacing**:
- Consistent padding/margin using Tailwind scale (4, 6, 8, 12, 16)
- Card spacing: p-6
- Section spacing: mb-8

**Components**:
- Cards: Rounded corners (rounded-lg), subtle shadow (shadow-md)
- Buttons: Rounded (rounded-md), padding (px-4 py-2), hover states
- Inputs: Full border (border), focus ring (focus:ring-2)

### Responsive Design

Target breakpoints:
- Mobile: < 640px (default)
- Tablet: 640px - 1024px (sm:, md:)
- Desktop: > 1024px (lg:, xl:)

Key responsive considerations:
- Dashboard grid: 1 column mobile, 2 columns tablet, 3 columns desktop
- Practice view: Full width on mobile, centered with max-width on desktop
- Image upload: Vertical layout mobile, side-by-side on desktop
- Navigation: Hamburger menu mobile, horizontal nav desktop

## Image Upload & Processing

### Upload Flow

1. **Client-side preparation**:
   - User selects image via ImageUploader component
   - Validate file type and size
   - Generate preview thumbnail
   - Display preview to user

2. **Request presigned URL**:
   - POST /vocab/upload with metadata (filename, contentType)
   - Backend generates S3 presigned POST URL
   - Return URL and fields to client

3. **Upload to S3**:
   - Use fetch or axios to PUT/POST file to presigned URL
   - Show upload progress bar
   - Handle upload errors (retry logic)

4. **Trigger extraction**:
   - POST /vocab/process with S3 key
   - Backend invokes extraction Lambda
   - Return vocabSetId

5. **Poll for results**:
   - GET /vocab/extraction/{vocabSetId} every 2 seconds
   - Status: pending → processing → complete/failed
   - On complete, redirect to ReviewView
   - On failed, show error and allow retry

### ImageUploader Component

**Features**:
- Drag-and-drop zone (dropzone-like UX)
- Click to browse file picker
- Image preview before upload
- File type validation (JPG, PNG, HEIC)
- File size validation (< 10MB)
- Progress bar during upload
- Error messages for validation failures

**Events**:
- `@upload-complete`: Emitted with vocabSetId on success
- `@upload-error`: Emitted with error message

## Practice Session Logic

### Answer Checking

Implement fuzzy matching to accept minor variations:

**Rules**:
- Strip diacritical marks (é → e, ç → c) for comparison
- Case-insensitive matching
- Trim leading/trailing whitespace
- Accept plurals (configurable tolerance)
- Ignore punctuation (periods, commas)

**Implementation**:
```javascript
function normalizeAnswer(text) {
  return text
    .toLowerCase()
    .trim()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // Remove diacritics
    .replace(/[.,!?;]/g, '')
}

function checkAnswer(userAnswer, correctAnswer) {
  const normalized = normalizeAnswer(userAnswer)
  const expected = normalizeAnswer(correctAnswer)
  return normalized === expected
}
```

### Session State Management

Track session data locally in practice store:

```javascript
{
  vocabSetId: 'uuid',
  questions: [
    { id: 'item1', german: 'Haus', french: 'maison' },
    // ...
  ],
  currentIndex: 0,
  answers: [
    { questionId: 'item1', userAnswer: 'maison', correct: true, timestamp: Date.now() },
    // ...
  ],
  startTime: Date.now()
}
```

On session completion:
- Calculate score, duration
- Submit to backend: POST /practice/complete
- Update local progress store
- Show SessionSummary modal

## Progress Tracking & Visualization

### Mastery Level Calculation

Each vocabulary item has a mastery level (0-5):

**Algorithm**:
- Start at level 0 (new word)
- Correct answer: +1 level (max 5)
- Incorrect answer: -1 level (min 0)
- Level 5 = mastered

**Storage**: Update Progress table after each session

### Chart.js Integration

Use Chart.js for visualizations:

**Bar Chart Example** (Mastery Distribution):
```javascript
{
  type: 'bar',
  data: {
    labels: ['New', 'Learning', 'Familiar', 'Mastered'],
    datasets: [{
      label: 'Words',
      data: [12, 35, 28, 15],
      backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#10b981']
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false
  }
}
```

**Line Chart Example** (Practice Activity):
```javascript
{
  type: 'line',
  data: {
    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    datasets: [{
      label: 'Words Practiced',
      data: [15, 0, 22, 18, 30, 12, 25],
      borderColor: '#3b82f6',
      fill: false
    }]
  }
}
```

## Error Handling

### Global Error Handling

Implement a global error handler:

**src/utils/errorHandler.js**:
```javascript
export function handleApiError(error) {
  if (error.response) {
    // Server responded with error status
    switch (error.response.status) {
      case 401:
        return 'Authentication required. Please log in.'
      case 403:
        return 'You do not have permission to perform this action.'
      case 404:
        return 'Resource not found.'
      case 500:
        return 'Server error. Please try again later.'
      default:
        return error.response.data?.message || 'An error occurred.'
    }
  } else if (error.request) {
    // Request made but no response
    return 'Network error. Please check your connection.'
  } else {
    // Something else happened
    return 'An unexpected error occurred.'
  }
}
```

### Component-Level Error Display

Use ErrorMessage component to display errors consistently:

```vue
<ErrorMessage v-if="error" :message="error" @dismiss="error = null" />
```

### Toast Notifications

Consider integrating a toast library (e.g., vue-toastification) for non-blocking notifications:
- Success: "Vocabulary set saved!"
- Info: "Extraction in progress..."
- Warning: "Some words may need review"
- Error: "Upload failed. Please try again."

## Performance Optimization

### Code Splitting

Use Vue Router lazy loading:
```javascript
{
  path: '/dashboard',
  component: () => import('./views/DashboardView.vue')
}
```

### Image Optimization

- Compress images before upload (client-side using browser-image-compression)
- Generate thumbnails for dashboard display
- Use S3 CloudFront with image transformation (resize on-the-fly)

### API Response Caching

Cache vocabulary sets in store to avoid redundant fetches:
- Store fetched vocab sets in local state
- Implement cache invalidation on updates/deletes
- Use Pinia persist plugin to cache across sessions

### Lazy Loading Components

For heavy components like Chart.js charts:
```javascript
const ProgressChart = defineAsyncComponent(() =>
  import('./components/progress/ProgressChart.vue')
)
```

## Testing Strategy

### Unit Tests (Vitest)

Test utilities and pure functions:
- `normalizeAnswer()` function with various inputs
- Validators (email, password strength)
- Formatters (dates, numbers)

### Component Tests (Vue Test Utils)

Test individual components:
- ImageUploader: file selection, validation, events
- AnswerInput: user input, submit behavior
- VocabCard: display logic, action buttons

### Integration Tests

Test store interactions:
- Auth store: login flow, token refresh
- Vocab store: CRUD operations with mocked API
- Practice store: session state management

### E2E Tests (Cypress or Playwright)

Test critical user journeys:
- Complete authentication flow (mock Cognito)
- Upload image → review → save workflow
- Practice session from start to completion
- View progress and statistics

## Deployment

### Build Process

Vite build command generates optimized static assets:
```bash
npm run build
```

Output in `dist/` directory:
- HTML, CSS, JS files with hashed filenames
- Assets (images, fonts) copied to dist
- Minified and tree-shaken code

### S3 + CloudFront Setup

1. **S3 Bucket Configuration**:
   - Create bucket: vocabtrainer-frontend-{env}
   - Enable static website hosting
   - Bucket policy: Allow CloudFront access
   - No public access (CloudFront only)

2. **CloudFront Distribution**:
   - Origin: S3 bucket
   - Default root object: index.html
   - Error pages: Redirect 404 to /index.html (SPA routing)
   - HTTPS only with ACM certificate
   - Cache behavior: Cache static assets (JS/CSS), no cache for index.html
   - Compress objects: Enabled (gzip/brotli)

3. **Deployment Script**:
   ```bash
   #!/bin/bash
   npm run build
   aws s3 sync dist/ s3://vocabtrainer-frontend-prod --delete
   aws cloudfront create-invalidation --distribution-id EXAMPLEID --paths "/*"
   ```

### Environment-Specific Configuration

Use `.env.production` for production values:
- API endpoint: Production API Gateway URL
- Cognito domain: Production user pool
- Callback URLs: Production CloudFront domain

### CI/CD Pipeline

Suggested GitHub Actions workflow:
1. Checkout code
2. Install dependencies
3. Run tests
4. Build production bundle
5. Deploy to S3
6. Invalidate CloudFront cache
7. Notify on completion

## Security Considerations

### Token Storage

- Store tokens in localStorage (acceptable for student app)
- Consider sessionStorage for higher security (token expires on tab close)
- Do NOT store in cookies (CSRF risk without proper configuration)
- Encrypt sensitive data if storing additional user info

### XSS Prevention

- Vue automatically escapes template content
- Sanitize any user-generated HTML (though not expected in this app)
- Use Content Security Policy headers via CloudFront

### CORS Configuration

API Gateway must allow:
- Origin: CloudFront domain
- Methods: GET, POST, PUT, DELETE
- Headers: Authorization, Content-Type
- Credentials: false (using Authorization header)

### Input Validation

Validate all user inputs client-side:
- File upload: type, size, dimensions
- Text inputs: max length, allowed characters
- Forms: required fields, format validation

Also validate server-side (defense in depth).

## Accessibility (a11y)

### WCAG 2.1 Compliance

Target Level AA compliance:

**Keyboard Navigation**:
- All interactive elements focusable via Tab
- Logical tab order
- Visible focus indicators (Tailwind focus:ring)
- Escape key closes modals

**Screen Reader Support**:
- Semantic HTML (nav, main, section, article)
- ARIA labels where needed (aria-label, aria-describedby)
- Alt text for images
- Form labels associated with inputs

**Color Contrast**:
- Minimum 4.5:1 for normal text
- Minimum 3:1 for large text
- Do not rely solely on color for feedback (use icons + color)

**Responsive Text**:
- Support browser zoom up to 200%
- Relative units (rem, em) instead of fixed pixels

## Internationalization (Future)

While initially German/French only, structure for future expansion:

- Use vue-i18n for UI translations
- Store vocabulary language pairs in database (extensible schema)
- UI language separate from vocabulary language
- Date/number formatting using Intl API

## Developer Experience

### Development Server

Vite dev server with HMR:
```bash
npm run dev
```

Runs on http://localhost:5173 by default.

### Mock API (Optional)

For frontend development without backend:
- Use MSW (Mock Service Worker) to intercept API calls
- Define mock responses for all endpoints
- Enable/disable via environment variable

### Linting & Formatting

- ESLint with Vue plugin for code quality
- Prettier for consistent formatting
- Pre-commit hooks with Husky and lint-staged

### Documentation

Document key patterns:
- Authentication flow diagram
- State management conventions
- Component communication patterns (props, events, slots)
- API integration examples

## Monitoring & Analytics (Optional)

Consider integrating:
- Google Analytics or Plausible for usage tracking
- Sentry for error tracking in production
- CloudWatch RUM for performance monitoring
- Custom events: upload success, practice completion, etc.

## Summary Checklist

When implementing this frontend, ensure:

- [ ] Vue 3 project set up with Vite and Tailwind CSS
- [ ] AWS Cognito integration with OAuth2 flow
- [ ] Protected routes with authentication guards
- [ ] API service with token management and refresh logic
- [ ] Pinia stores for auth, vocab, practice, and progress
- [ ] All seven main views implemented
- [ ] Image upload with S3 presigned URLs
- [ ] Practice session with fuzzy answer matching
- [ ] Progress visualization with Chart.js
- [ ] Responsive design for mobile/tablet/desktop
- [ ] Error handling and user feedback
- [ ] Deployment to S3 + CloudFront configured
- [ ] Environment-specific configuration managed
- [ ] Basic accessibility features implemented
- [ ] Testing coverage for critical flows

This comprehensive guide should enable an AI coding assistant to implement a production-ready Vue.js frontend for the VocabTrainer application.