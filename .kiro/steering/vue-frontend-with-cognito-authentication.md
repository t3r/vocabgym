# Vue Frontend with Cognito Authentication

## Project Context

This document describes the frontend implementation for VocabTrainer, a web-based vocabulary training application for German Gymnasium students. The application supports multiple target languages (French, English, Spanish, Italian) with German as the source language. Students scan workbook pages, extract vocabulary through AI, and practice with typing-based exercises. Teachers can create leagues, assign vocabulary sets, and track student progress.

## Technology Stack

- **Framework**: Vue 3 with Composition API
- **Build Tool**: Vite
- **Styling**: Tailwind CSS (with full dark mode support)
- **State Management**: Pinia
- **Routing**: Vue Router
- **HTTP Client**: Axios
- **Authentication**: AWS Cognito (OAuth2 flow with hosted UI)
- **Charts**: Chart.js or similar for progress visualization
- **Deployment**: AWS S3 + CloudFront CDN

## Architecture Overview

The frontend is a Single Page Application (SPA) that communicates with a serverless backend via REST API. Authentication is handled entirely by AWS Cognito using the OAuth2 authorization code flow with PKCE. The Cognito hosted UI manages login, registration, and password reset flows.

The UI language is German throughout. Students see Du-Form ("Dein Fortschritt", "Übe jetzt"), teachers see Sie-Form ("Ihre Liga", "Verwalten Sie Ihre Vokabelsets").

### High-Level Flow

1. User accesses application via CloudFront URL
2. Unauthenticated users are redirected to Cognito hosted UI
3. After successful authentication, Cognito redirects back with authorization code
4. Frontend exchanges code for JWT tokens (handled by Cognito SDK)
5. Role is extracted from the ID token's `cognito:groups` claim (e.g., `teachers` group)
6. All API requests include JWT token in Authorization header
7. API Gateway validates token against Cognito before invoking Lambda functions

## Project Structure

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── assets/
│   │   └── styles/
│   │       └── main.css          # Global styles including dark mode for form elements
│   ├── components/
│   │   ├── common/
│   │   │   ├── AppHeader.vue     # Includes inline display name editor, dark mode toggle
│   │   │   ├── LoadingSpinner.vue
│   │   │   └── ErrorMessage.vue
│   │   ├── vocab/
│   │   │   ├── VocabCard.vue
│   │   │   ├── VocabList.vue
│   │   │   └── VocabTable.vue
│   │   ├── upload/
│   │   │   ├── ImageUploader.vue  # Multi-image support, targetLanguage selector
│   │   │   └── UploadProgress.vue
│   │   ├── practice/
│   │   │   ├── PracticeCard.vue
│   │   │   ├── AnswerInput.vue
│   │   │   ├── SessionSummary.vue
│   │   │   └── Lernhinweis.vue    # Learning hint feedback component
│   │   ├── progress/
│   │   │   ├── ProgressChart.vue
│   │   │   └── StatsCard.vue
│   │   └── league/
│   │       ├── LeagueCard.vue
│   │       ├── Leaderboard.vue
│   │       └── JoinLeagueModal.vue
│   ├── views/
│   │   ├── LandingView.vue
│   │   ├── DashboardView.vue
│   │   ├── UploadView.vue
│   │   ├── ReviewView.vue
│   │   ├── PracticeView.vue
│   │   ├── ProgressView.vue
│   │   ├── VocabDetailView.vue
│   │   ├── LeagueView.vue        # League management and leaderboard
│   │   └── HelpView.vue          # Help and documentation
│   ├── router/
│   │   └── index.js
│   ├── stores/
│   │   ├── auth.js               # Includes role, leagueId, _extractRoleFromToken()
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

- **User Pool ID**: `eu-central-1_oc5HH7k2w`
- **Sign-in Options**: Email
- **MFA**: Optional (recommended: OFF for students)
- **Password Policy**:
  - Minimum length: 8 characters
  - Require uppercase, lowercase, numbers
  - No special characters required (student-friendly)
- **Email Verification**: Required
- **Hosted UI Domain**: vocabtrainer-auth-{env}.auth.eu-central-1.amazoncognito.com
- **Groups**:
  - `teachers` — Users in this group have the teacher role. All other users are students by default.

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

### Token Claims

The ID token includes a `cognito:groups` claim containing an array of group names the user belongs to. The frontend extracts the user role from this claim:

- If `cognito:groups` contains `"teachers"` → role is `teacher`
- Otherwise → role is `student`

## Environment Configuration

Create `.env` and `.env.production` files:

```
VITE_AWS_REGION=eu-central-1
VITE_COGNITO_USER_POOL_ID=eu-central-1_oc5HH7k2w
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

Pinia store managing authentication state, including role-based access and league membership.

**State**:
```javascript
{
  user: null,           // { sub, email, displayName, ... }
  accessToken: null,
  idToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
  role: null,           // 'teacher' | 'student' — extracted from id_token cognito:groups claim
  leagueId: null        // Persisted in localStorage, set when student joins a league
}
```

**Actions**:
- `login()`: Initiates OAuth flow
- `handleAuthCallback(code)`: Processes callback, calls `_extractRoleFromToken()`
- `logout()`: Clears auth state (tokens, role, leagueId)
- `refreshSession()`: Refreshes tokens, re-extracts role
- `loadUserFromStorage()`: Restores session on page load, restores leagueId from localStorage
- `checkTokenExpiry()`: Validates token freshness
- `_extractRoleFromToken()`: Decodes the ID token, reads `cognito:groups` claim. Sets `role` to `'teacher'` if groups contain `'teachers'`, otherwise `'student'`.

**Getters**:
- `isTeacher`: Returns `role === 'teacher'`
- `isStudent`: Returns `role === 'student'`
- `displayName`: Returns user's display name (never email)

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
| `/league` | LeagueView | Yes | League management and leaderboard |
| `/help` | HelpView | Yes | Help and documentation |

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
- Hero section explaining the app (German UI text)
- "Los geht's" button triggering Cognito login
- Brief feature overview (Scannen, Überprüfen, Üben)
- Mentions multi-language support (FR, EN, ES, IT)
- Responsive design for mobile/tablet/desktop

**Behavior**:
- If user is already authenticated, redirect to /dashboard
- Otherwise, show marketing content

### DashboardView.vue

**Purpose**: Main hub showing all vocabulary sets

**Layout**:
- Header with display name (editable inline via AppHeader), logout button, dark mode toggle
- "Neue Seite hochladen" prominent upload button
- Grid/list of vocabulary sets with:
  - Thumbnail of source image
  - Title (e.g., "Kapitel 3: L'école")
  - Target language indicator (FR/EN/ES/IT flag or badge)
  - Item count (e.g., "24 Wörter")
  - Last practiced date
  - Quick action buttons: Üben, Ansehen, Löschen
- Filter/sort options (by date, chapter, mastery, target language)
- Quick stats widget: total words, mastery percentage, practice streak

**Role-specific behavior**:
- **Students**: See their own vocab sets, league leaderboard widget
- **Teachers**: Additional "Liga verwalten" section, ability to assign vocab sets to league

**State Management**:
- Uses vocab store to fetch and display all vocab sets
- Real-time updates when new sets are added

### AppHeader.vue

**Purpose**: Global header component

**Features**:
- Display name shown prominently (never email)
- Inline display name editor: click to edit, Enter to save, Escape to cancel
- Dark mode toggle button
- Navigation links
- Logout button
- Role indicator (Lehrer/Schüler badge for teachers)
- League name display if leagueId is set

### UploadView.vue

**Purpose**: Upload and process workbook images

**Components Used**:
- ImageUploader component (drag-and-drop zone)
- UploadProgress component (shows processing status)
- Target language selector (FR/EN/ES/IT dropdown)

**Flow**:
1. User selects target language for this vocabulary set
2. User drags images or clicks to browse (multi-image supported)
3. Image previews shown for all selected images
4. "Verarbeiten" button sends images to backend
5. Progress indicator during upload and extraction
6. On completion, redirect to ReviewView with vocabSetId

**Technical Details**:
- Accept JPG, PNG formats only — HEIC is rejected (iOS auto-converts to JPG/PNG)
- Client-side validation (file size < 10MB, image dimensions)
- Multi-image upload: multiple images can be uploaded for a single vocab set
- Target language selector is required before upload
- Request presigned S3 URL from backend
- Upload directly to S3 using presigned URL
- Trigger extraction Lambda via API
- Poll extraction status or use WebSocket for real-time updates

### ReviewView.vue

**Purpose**: Review and edit extracted vocabulary before approval

**Layout**:
- Left panel: Original workbook image(s) — scrollable if multi-image
- Right panel: Editable table of extracted vocabulary
  - Source column (German)
  - Target column (language depends on vocab set's targetLanguage)
  - Delete row button
  - Add row button
- Metadata inputs: Title, Chapter, Page Number, Topic
- Target language display (read-only, set during upload)
- "Speichern & Freigeben" button (primary action)
- "Abbrechen" button

**Features**:
- Inline editing of source/target pairs
- Validation: no empty fields
- Highlight potential extraction errors (empty cells, unusual characters)
- Keyboard shortcuts: Tab to move between cells, Enter to add row

**State Management**:
- Fetch extraction results from API on mount
- Local state for editing before save
- On save, update vocab store and redirect to dashboard

### PracticeView.vue

**Purpose**: Interactive practice session with smart repetition

**Components Used**:
- PracticeCard (displays question)
- AnswerInput (text input with submit)
- SessionSummary (modal showing results)
- Lernhinweis (learning hint feedback component)

**Session Flow**:
1. Load questions from selected vocab set
2. Smart repetition: prioritize words with lower mastery, recent errors, and error patterns
3. For each question:
   - Display source word (German) or target word (based on direction)
   - Show text input for answer
   - User types and submits (Enter key or button)
   - Immediate feedback: correct (green) or incorrect (red)
   - If incorrect, show correct answer and **Lernhinweis** (learning hint)
   - "Weiter" button to continue
4. After all questions, show SessionSummary modal:
   - Score: X/Y correct
   - Time taken
   - List of mistakes with Lernhinweise
   - Error pattern analysis (e.g., "Du verwechselst oft ähnliche Wörter")
   - "Nochmal üben" or "Zurück zum Dashboard" buttons

**Lernhinweis (Learning Hint) Feature**:
- After an incorrect answer, the system provides a contextual learning hint
- Hints can include: mnemonic aids, common confusion patterns, related words
- Displayed in a distinct card below the feedback
- Helps students understand why they made an error

**Smart Repetition**:
- Words answered incorrectly appear more frequently in subsequent sessions
- Error patterns are tracked (e.g., confusing similar-sounding words)
- Algorithm weights: mastery level, time since last practice, error frequency

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
- Full dark mode support

### ProgressView.vue

**Purpose**: Visualize learning progress

**Layout**:
- Overall statistics card:
  - Total vocabulary sets
  - Total words learned
  - Average mastery level
  - Practice streak (days) — 🔥 streak icon
- Charts:
  - Bar chart: mastery distribution (how many words at each mastery level)
  - Line chart: practice activity over time
  - Pie chart: vocabulary by target language
- Recent practice sessions table
- Words needing review (low mastery level)

**Components Used**:
- ProgressChart (Chart.js wrapper)
- StatsCard (reusable statistic display)

**Data Sources**:
- Fetch from /progress/overview API
- Aggregate data from practice sessions
- Calculate mastery levels based on correct/incorrect counts

### LeagueView.vue

**Purpose**: League management, leaderboard, and social features

**Teacher View (Sie-Form)**:
- "Neue Liga erstellen" button → generates a 6-character join code
- Display current league with join code (copyable)
- List of league members with their display names and stats
- Assign vocab sets to league members
- Leaderboard showing member rankings
- Streak tracking for all members

**Student View (Du-Form)**:
- "Liga beitreten" button → enter 6-character code in JoinLeagueModal
- Current league info display
- Leaderboard with rankings (display names only, never emails)
- Personal streak display
- Assigned vocab sets from teacher

**Components Used**:
- LeagueCard (league info display)
- Leaderboard (ranked member list with streaks and scores)
- JoinLeagueModal (code entry dialog)

### HelpView.vue

**Purpose**: Help documentation and FAQ

**Features**:
- Getting started guide (German UI)
- How to upload and process images
- Practice tips
- League system explanation
- FAQ section
- Contact/feedback option

## State Management (Pinia Stores)

### Auth Store (auth.js)

Manages user authentication state, role, and league membership.

**State**:
```javascript
{
  user: null,           // { sub, email, displayName, ... }
  accessToken: null,
  idToken: null,
  refreshToken: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,
  role: null,           // 'teacher' | 'student'
  leagueId: null        // Persisted in localStorage
}
```

**Actions**:
- `login()`: Initiates OAuth flow
- `handleAuthCallback(code)`: Processes callback, extracts role from token
- `logout()`: Clears auth state
- `refreshSession()`: Refreshes tokens, re-extracts role
- `loadUserFromStorage()`: Restores session on page load, restores leagueId from localStorage
- `checkTokenExpiry()`: Validates token freshness
- `_extractRoleFromToken()`: Decodes the ID token JWT, reads `cognito:groups` claim array. If it contains `'teachers'`, sets `role = 'teacher'`. Otherwise `role = 'student'`.

**Getters**:
- `isTeacher`: Returns `role === 'teacher'`
- `isStudent`: Returns `role === 'student'`
- `displayName`: Returns user's display name (never email)

### Vocab Store (vocab.js)

**State**:
```javascript
{
  vocabSets: [],          // Array of vocab set objects
  currentVocabSet: null,  // Currently viewed/edited vocab set
  isLoading: false,
  error: null
}
```

Each vocab set object includes:
```javascript
{
  vocabSetId: 'uuid',
  title: 'Kapitel 3',
  targetLanguage: 'fr',   // 'fr' | 'en' | 'es' | 'it'
  sourceLanguage: 'de',   // Always German
  itemCount: 24,
  items: [
    { itemId: 'uuid', source: 'das Haus', target: 'la maison', order: 1 }
  ],
  // ...
}
```

**Actions**:
- `fetchVocabSets()`: Load all vocab sets for user
- `fetchVocabSet(id)`: Load specific vocab set with items
- `createVocabSet(data)`: Create new vocab set (includes targetLanguage)
- `updateVocabSet(id, data)`: Update vocab set
- `deleteVocabSet(id)`: Delete vocab set
- `uploadImages(files, targetLanguage)`: Handle multi-image upload flow
- `processImages(imageKeys, targetLanguage)`: Trigger extraction

**Getters**:
- `getVocabSetById(id)`: Find specific vocab set
- `sortedVocabSets`: Return vocab sets sorted by date
- `vocabSetsByChapter`: Group vocab sets by chapter
- `vocabSetsByLanguage`: Group vocab sets by target language

### Practice Store (practice.js)

**State**:
```javascript
{
  currentSession: null,   // { questions, answers, startTime, vocabSetId }
  sessionHistory: [],     // Array of completed sessions
  errorPatterns: {},      // Tracked error patterns per vocabSetId
  isLoading: false,
  error: null
}
```

**Actions**:
- `startSession(vocabSetId, options)`: Initialize practice session with smart repetition
- `submitAnswer(answer)`: Check answer and store result
- `nextQuestion()`: Move to next question
- `completeSession()`: Finalize and save session
- `fetchSessionHistory()`: Load past sessions
- `generateLernhinweis(itemId, userAnswer, correctAnswer)`: Generate learning hint for incorrect answer

**Getters**:
- `currentQuestion`: Get current question object
- `sessionProgress`: Calculate percentage complete
- `sessionScore`: Calculate current score

### Progress Store (progress.js)

**State**:
```javascript
{
  overallStats: null,       // { totalWords, masteryAverage, practiceStreak }
  vocabSetProgress: {},     // Map of vocabSetId -> progress data
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

Extend default theme with custom colors, fonts, dark mode, and utilities:

```javascript
module.exports = {
  content: ['./index.html', './src/**/*.{vue,js,ts}'],
  darkMode: 'class',
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

### Dark Mode

Full dark mode support is implemented using Tailwind's `class` strategy:

- Toggle button in AppHeader switches between light and dark mode
- Preference persisted in localStorage
- Global dark mode CSS in `main.css` covers all form elements (inputs, selects, textareas, buttons)
- All components use `dark:` Tailwind variants for backgrounds, text, borders
- Charts and visualizations adapt to dark mode color scheme

**Global Dark Mode CSS (main.css)**:
```css
/* Global dark mode styles for form elements */
.dark input,
.dark select,
.dark textarea {
  background-color: #1f2937;
  border-color: #4b5563;
  color: #f9fafb;
}

.dark input::placeholder,
.dark textarea::placeholder {
  color: #9ca3af;
}
```

### Design System Guidelines

**Colors**:
- Primary: Blue (#3b82f6) for CTAs, links, active states
- Success: Green (#10b981) for correct answers, completion
- Error: Red (#ef4444) for incorrect answers, validation errors
- Neutral: Gray scale for text, backgrounds, borders
- Dark mode: Slate/gray dark backgrounds, adjusted text contrast

**Typography**:
- Headings: Bold, larger sizes (text-2xl to text-4xl)
- Body: Regular weight, comfortable reading size (text-base)
- Vocabulary words: Larger (text-xl), clear font

**Spacing**:
- Consistent padding/margin using Tailwind scale (4, 6, 8, 12, 16)
- Card spacing: p-6
- Section spacing: mb-8

**Components**:
- Cards: Rounded corners (rounded-lg), subtle shadow (shadow-md), dark:bg-gray-800
- Buttons: Rounded (rounded-md), padding (px-4 py-2), hover states
- Inputs: Full border (border), focus ring (focus:ring-2), dark mode variants

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

1. **Target language selection**:
   - User selects target language (FR/EN/ES/IT) from dropdown
   - This is required before any upload can proceed

2. **Client-side preparation**:
   - User selects one or more images via ImageUploader component
   - Validate file type and size per image
   - HEIC files are rejected with a message (iOS auto-converts to JPG/PNG)
   - Generate preview thumbnails for all selected images
   - Display previews to user

3. **Request presigned URLs**:
   - POST /vocab/upload with metadata (filenames, contentTypes, targetLanguage)
   - Backend generates S3 presigned POST URLs for each image
   - Return URLs and fields to client

4. **Upload to S3**:
   - Use fetch or axios to PUT/POST each file to its presigned URL
   - Show upload progress bar (aggregate across all images)
   - Handle upload errors (retry logic)

5. **Trigger extraction**:
   - POST /vocab/process with S3 keys and targetLanguage
   - Backend invokes extraction Lambda
   - Return vocabSetId

6. **Poll for results**:
   - GET /vocab/extraction/{vocabSetId} every 2 seconds
   - Status: pending → processing → complete/failed
   - On complete, redirect to ReviewView
   - On failed, show error and allow retry

### ImageUploader Component

**Features**:
- Drag-and-drop zone (dropzone-like UX)
- Click to browse file picker
- Multi-image selection supported
- Image preview before upload (thumbnail grid)
- File type validation: JPG and PNG only. HEIC rejected with user-friendly message ("HEIC wird nicht unterstützt. Bitte verwende JPG oder PNG.")
- File size validation (< 10MB per image)
- Target language selector (dropdown: Französisch, Englisch, Spanisch, Italienisch)
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

### Smart Repetition

The practice session uses smart repetition to optimize learning:

- Words with lower mastery levels appear more frequently
- Recently incorrect words are prioritized
- Error patterns are tracked and used to generate targeted practice
- The algorithm combines: mastery level weight, time since last practice, error frequency

### Lernhinweis (Learning Hint)

After an incorrect answer, the system displays a contextual learning hint:

- Highlights the difference between user's answer and correct answer
- Points out common confusion patterns (e.g., false friends between languages)
- Provides mnemonic aids when available
- Displayed in a visually distinct card below the answer feedback

### Session State Management

Track session data locally in practice store:

```javascript
{
  vocabSetId: 'uuid',
  targetLanguage: 'fr',
  questions: [
    { id: 'item1', source: 'Haus', target: 'maison' },
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
- Show SessionSummary modal with Lernhinweise for incorrect answers

## League System

### Overview

The league system enables social learning and teacher-student interaction:

- **Teachers** create leagues and receive a unique 6-character join code
- **Students** join leagues using the 6-character code
- Leagues have a leaderboard based on practice activity and mastery
- Teachers can assign specific vocab sets to their league
- Streak tracking motivates consistent practice

### Teacher Features

- Create a new league (generates 6-char alphanumeric code)
- View league members and their progress
- Assign vocab sets to the league
- View leaderboard with all member statistics
- Remove members from league

### Student Features

- Join a league by entering the 6-character code (stored as leagueId in auth store / localStorage)
- View league leaderboard (display names only, never emails)
- See assigned vocab sets from teacher
- Track personal streak within league context

### Leaderboard

- Ranked by total mastery score across all vocab sets
- Shows: rank, display name, mastery %, streak 🔥, total words practiced
- Updates after each completed practice session

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
    labels: ['Neu', 'Lernend', 'Bekannt', 'Gemeistert'],
    datasets: [{
      label: 'Wörter',
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
    labels: ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'],
    datasets: [{
      label: 'Geübte Wörter',
      data: [15, 0, 22, 18, 30, 12, 25],
      borderColor: '#3b82f6',
      fill: false
    }]
  }
}
```

## UI Language & Localization

### German UI

The entire UI is in German:

- **Students (Du-Form)**: "Dein Fortschritt", "Übe jetzt", "Lade ein Bild hoch", "Weiter", "Zurück zum Dashboard"
- **Teachers (Sie-Form)**: "Ihre Liga", "Verwalten Sie Ihre Vokabelsets", "Erstellen Sie eine neue Liga"

The form of address switches based on the `role` from the auth store:
- `role === 'student'` → Du-Form throughout
- `role === 'teacher'` → Sie-Form throughout

### Display Names

- Users set their display name via the inline editor in AppHeader
- Display names are used everywhere: leaderboard, league member lists, session history
- Email addresses are never exposed in the UI
- If no display name is set, a placeholder prompt is shown ("Name eingeben")

## Error Handling

### Global Error Handling

Implement a global error handler:

**src/utils/errorHandler.js**:
```javascript
export function handleApiError(error) {
  if (error.response) {
    switch (error.response.status) {
      case 401:
        return 'Bitte melde dich erneut an.'
      case 403:
        return 'Keine Berechtigung für diese Aktion.'
      case 404:
        return 'Nicht gefunden.'
      case 500:
        return 'Serverfehler. Bitte versuche es später erneut.'
      default:
        return error.response.data?.message || 'Ein Fehler ist aufgetreten.'
    }
  } else if (error.request) {
    return 'Netzwerkfehler. Bitte prüfe deine Verbindung.'
  } else {
    return 'Ein unerwarteter Fehler ist aufgetreten.'
  }
}
```

### Component-Level Error Display

Use ErrorMessage component to display errors consistently:

```vue
<ErrorMessage v-if="error" :message="error" @dismiss="error = null" />
```

### Toast Notifications

Use vue-toastification or similar for non-blocking notifications (German text):
- Success: "Vokabelset gespeichert!"
- Info: "Extraktion läuft..."
- Warning: "Einige Wörter sollten überprüft werden"
- Error: "Upload fehlgeschlagen. Bitte versuche es erneut."

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
- `_extractRoleFromToken()` with different token payloads
- Validators (email, password strength)
- Formatters (dates, numbers)

### Component Tests (Vue Test Utils)

Test individual components:
- ImageUploader: file selection, HEIC rejection, multi-image, validation, events
- AnswerInput: user input, submit behavior
- VocabCard: display logic, action buttons, target language badge
- Lernhinweis: hint display, dismiss behavior
- JoinLeagueModal: code entry, validation

### Integration Tests

Test store interactions:
- Auth store: login flow, token refresh, role extraction, leagueId persistence
- Vocab store: CRUD operations with mocked API, multi-language support
- Practice store: session state management, smart repetition, error patterns

### E2E Tests (Cypress or Playwright)

Test critical user journeys:
- Complete authentication flow (mock Cognito)
- Upload image → review → save workflow (with target language selection)
- Practice session from start to completion (with Lernhinweise)
- League join flow (student) and league creation flow (teacher)
- View progress and statistics
- Dark mode toggle

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
- leagueId stored in localStorage for persistence across sessions

### Role Extraction

- Role is derived from `cognito:groups` claim in the ID token
- The `_extractRoleFromToken()` method decodes the JWT and checks for `teachers` group membership
- Role is re-extracted on every token refresh to stay in sync with Cognito group changes

### XSS Prevention

- Vue automatically escapes template content
- Sanitize any user-generated HTML (display names, vocab content)
- Use Content Security Policy headers via CloudFront

### CORS Configuration

API Gateway must allow:
- Origin: CloudFront domain
- Methods: GET, POST, PUT, DELETE
- Headers: Authorization, Content-Type
- Credentials: false (using Authorization header)

### Input Validation

Validate all user inputs client-side:
- File upload: type (JPG/PNG only, no HEIC), size, dimensions
- Text inputs: max length, allowed characters
- Display names: sanitized, max length
- League codes: exactly 6 alphanumeric characters
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
- Minimum 4.5:1 for normal text (both light and dark mode)
- Minimum 3:1 for large text
- Do not rely solely on color for feedback (use icons + color)
- Dark mode contrast ratios validated

**Responsive Text**:
- Support browser zoom up to 200%
- Relative units (rem, em) instead of fixed pixels

## Vocabulary Data Model

### Field Naming Convention

All vocabulary fields use language-agnostic names:

- `source` — The German word/phrase (source language is always German)
- `target` — The translation in the target language (FR/EN/ES/IT)
- `targetLanguage` — ISO code for the target language: `fr`, `en`, `es`, `it`
- `sourceLanguage` — Always `de` (German)

**Example vocab item**:
```javascript
{
  itemId: 'uuid',
  source: 'das Haus',
  target: 'la maison',
  notes: '',
  order: 1
}
```

**Example vocab set**:
```javascript
{
  vocabSetId: 'uuid',
  title: 'Kapitel 3: À la maison',
  sourceLanguage: 'de',
  targetLanguage: 'fr',
  itemCount: 24,
  items: [/* ... */]
}
```

The old `german`/`french` field names are not used. All code references `source`/`target` throughout.

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
- Role extraction from Cognito tokens
- State management conventions
- Component communication patterns (props, events, slots)
- API integration examples
- Multi-language vocab set handling

## Summary Checklist

When implementing this frontend, ensure:

- [ ] Vue 3 project set up with Vite and Tailwind CSS
- [ ] Full dark mode support with global CSS for form elements
- [ ] AWS Cognito integration with OAuth2 flow (User Pool: eu-central-1_oc5HH7k2w)
- [ ] Role extraction from ID token cognito:groups claim (`teachers` group)
- [ ] Protected routes with authentication guards
- [ ] API service with token management and refresh logic
- [ ] Pinia stores for auth (with role, leagueId), vocab, practice, and progress
- [ ] All views implemented: Landing, Dashboard, Upload, Review, Practice, Progress, VocabDetail, League, Help
- [ ] Multi-language support: target language selector (FR/EN/ES/IT) during upload
- [ ] source/target field naming throughout (not german/french)
- [ ] Image upload with S3 presigned URLs (JPG/PNG only, HEIC rejected, multi-image)
- [ ] Practice session with fuzzy answer matching, smart repetition, and Lernhinweis feedback
- [ ] League system: teacher creates league, students join with 6-char code, leaderboard
- [ ] German UI throughout: Du-Form for students, Sie-Form for teachers
- [ ] Display names via inline editor in AppHeader (email never exposed)
- [ ] Progress visualization with Chart.js
- [ ] Responsive design for mobile/tablet/desktop
- [ ] Error handling and user feedback (German messages)
- [ ] Deployment to S3 + CloudFront configured
- [ ] Environment-specific configuration managed
- [ ] Accessibility features implemented (both light and dark mode)
- [ ] Testing coverage for critical flows including role extraction and league features
