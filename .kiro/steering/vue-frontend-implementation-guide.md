# Vue Frontend Implementation Guide

## Project Context

This is the frontend implementation guide for **VocabGym**, a web-based vocabulary training application for German students. The application allows students to scan workbook pages, extract vocabulary automatically using AI, review and edit the extracted content, and practice with typing-based exercises. It supports multiple target languages (French, English, Spanish, Italian) with German as the source language. The entire UI is in German, using Du-Form for students and Sie-Form for teachers.

## Technology Stack

- **Framework**: Vue 3 with Composition API
- **Build Tool**: Vite
- **Styling**: Tailwind CSS with full dark mode support (`dark:` variants)
- **State Management**: Pinia
- **Routing**: Vue Router
- **HTTP Client**: Axios
- **Charts**: Chart.js with vue-chartjs wrapper
- **Authentication**: AWS Cognito (OAuth2 flow with hosted UI)

## Architecture Overview

The frontend is a single-page application (SPA) that communicates with a serverless backend via REST API (AWS API Gateway + Lambda). It is deployed as a static site on S3 and served through CloudFront CDN.

### Key User Flows

1. **Authentication Flow**: User clicks login → redirected to Cognito hosted UI → OAuth callback → token stored → role extracted from `cognito:groups` → redirect to dashboard
2. **Upload Flow**: User selects target language → drags/drops one or more workbook images → presigned URLs requested → direct upload to S3 → trigger extraction per image → poll for results
3. **Review Flow**: Extraction complete → display vertical layout with per-image item grouping → user approves/edits inline → save to backend
4. **Practice Flow**: User selects vocab set → smart repetition loads questions (weak words prioritized) → type answer → immediate feedback → session summary with error pattern analysis (Lernhinweis)
5. **League Flow**: Teacher creates league → students join with 6-character code → practice earns points → leaderboard shows rankings and streaks

## Project Structure

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── assets/
│   │   ├── logo.svg
│   │   └── styles/
│   │       └── main.css
│   ├── components/
│   │   ├── auth/
│   │   │   ├── LoginButton.vue
│   │   │   └── LogoutButton.vue
│   │   ├── common/
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppFooter.vue
│   │   │   ├── LoadingSpinner.vue
│   │   │   ├── Modal.vue
│   │   │   └── Toast.vue
│   │   ├── dashboard/
│   │   │   ├── VocabSetCard.vue
│   │   │   ├── StatsOverview.vue
│   │   │   └── GoalBanner.vue
│   │   ├── upload/
│   │   │   ├── ImageDropzone.vue
│   │   │   ├── UploadProgress.vue
│   │   │   └── ExtractionStatus.vue
│   │   ├── review/
│   │   │   ├── VocabTable.vue
│   │   │   ├── VocabTableRow.vue
│   │   │   ├── MetadataForm.vue
│   │   │   └── ImagePreview.vue
│   │   ├── practice/
│   │   │   ├── QuestionCard.vue
│   │   │   ├── AnswerInput.vue
│   │   │   ├── FeedbackDisplay.vue
│   │   │   ├── ProgressBar.vue
│   │   │   ├── SessionSummary.vue
│   │   │   └── PronounceButton.vue
│   │   └── progress/
│   │       ├── ProgressChart.vue
│   │       ├── MasteryIndicator.vue
│   │       └── SessionHistory.vue
│   ├── composables/
│   │   ├── useAuth.js
│   │   ├── useApi.js
│   │   ├── useUpload.js
│   │   ├── usePractice.js
│   │   └── useToast.js
│   ├── router/
│   │   └── index.js
│   ├── stores/
│   │   ├── auth.js
│   │   ├── vocab.js
│   │   ├── practice.js
│   │   └── ui.js
│   ├── services/
│   │   ├── api.js
│   │   ├── cognito.js
│   │   ├── storage.js
│   │   └── tts.js
│   ├── utils/
│   │   ├── validators.js
│   │   ├── formatters.js
│   │   ├── fuzzyMatch.js
│   │   └── languages.js
│   ├── views/
│   │   ├── LandingView.vue
│   │   ├── CallbackView.vue
│   │   ├── DashboardView.vue
│   │   ├── UploadView.vue
│   │   ├── ReviewView.vue
│   │   ├── PracticeView.vue
│   │   ├── ProgressView.vue
│   │   ├── VocabSetDetailView.vue
│   │   ├── LeagueView.vue
│   │   ├── LeagueJoinView.vue
│   │   ├── HelpView.vue
│   │   ├── PrivacyView.vue
│   │   ├── ImpressumView.vue
│   │   └── NotFoundView.vue
│   ├── App.vue
│   └── main.js
├── .env.development
├── .env.production
├── index.html
├── package.json
├── tailwind.config.js
├── vite.config.js
└── README.md
```

## Multi-Language Support

### utils/languages.js

Defines supported target languages, source language (German), articles, and gender explanations.

**Supported Target Languages:**
- `fr` — Französisch 🇫🇷
- `en` — Englisch 🇬🇧
- `es` — Spanisch 🇪🇸
- `it` — Italienisch 🇮🇹

**Source Language:** German (`de`) — always the source.

**Exports:**
- `SUPPORTED_LANGUAGES`: Object keyed by language code, each with `code`, `name` (German), `flag`, `articles`, `articleGenders`
- `SOURCE_LANGUAGE`: German language config
- `DEFAULT_TARGET_LANGUAGE`: `'fr'`
- `getLanguage(code)`: Returns language config
- `getLanguageName(code)`: Returns German name of language
- `getLanguageFlag(code)`: Returns flag emoji
- `getAllArticleGenders(targetCode)`: Merged article-to-gender mappings for source and target

**Data Model Note:** Vocabulary items use `source`/`target` field names (not `german`/`french`). Legacy `german`/`french` fields are still handled for backward compatibility in the review and practice views.

## Environment Configuration

### .env.development
```
VITE_API_BASE_URL=http://localhost:3000/dev
VITE_COGNITO_DOMAIN=vocab-trainer-dev.auth.eu-central-1.amazoncognito.com
VITE_COGNITO_CLIENT_ID=your-dev-client-id
VITE_COGNITO_REDIRECT_URI=http://localhost:5173/callback
VITE_COGNITO_LOGOUT_URI=http://localhost:5173
```

### .env.production
```
VITE_API_BASE_URL=https://api.vocabtrainer.com
VITE_COGNITO_DOMAIN=vocab-trainer.auth.eu-central-1.amazoncognito.com
VITE_COGNITO_CLIENT_ID=your-prod-client-id
VITE_COGNITO_REDIRECT_URI=https://vocabtrainer.com/callback
VITE_COGNITO_LOGOUT_URI=https://vocabtrainer.com
```

## Core Services

### services/cognito.js

This service handles all Cognito-related authentication operations including OAuth flow, token management, and user info retrieval.

**Key Functions:**
- `initiateLogin()`: Redirect to Cognito hosted UI
- `handleCallback(code)`: Exchange authorization code for tokens
- `logout()`: Clear tokens and redirect to Cognito logout
- `getAccessToken()`: Retrieve valid access token (refresh if expired)
- `getUserInfo()`: Fetch user profile from Cognito
- `isAuthenticated()`: Check if user has valid tokens
- `refreshTokens()`: Use refresh token to get new access/id tokens

**Implementation Notes:**
- Store tokens in localStorage with key prefix `vocab_trainer_`
- Implement automatic token refresh before expiry
- Handle token expiration gracefully with redirect to login
- Use PKCE (Proof Key for Code Exchange) for OAuth flow security

### services/api.js

Axios instance configured for API communication with interceptors for authentication and error handling.

**Configuration:**
- Base URL from environment variable
- Request interceptor: Add `Authorization: Bearer {token}` header
- Response interceptor: Handle 401 (redirect to login), 403 (show error), network errors
- Retry logic for transient failures (3 retries with exponential backoff)

**API Methods:**

**Vocabulary Management:**
- `uploadImage()`: POST to get presigned S3 URL
- `triggerExtraction(imageKey)`: POST to start Textract processing
- `pollExtraction(vocabSetId)`: GET extraction status (poll every 2s)
- `getExtractionResults(vocabSetId)`: GET extracted vocabulary
- `saveVocabSet(vocabSetId, data)`: PUT to approve/update vocab set
- `listVocabSets()`: GET all vocab sets for user
- `getVocabSet(vocabSetId)`: GET single vocab set details
- `deleteVocabSet(vocabSetId)`: DELETE vocab set

**Practice:**
- `startPracticeSession(vocabSetId, options)`: POST to create session (backend applies smart repetition)
- `submitAnswer(sessionId, questionId, answer)`: POST answer, get feedback
- `completeSession(sessionId)`: POST to finalize session — returns `leagueUpdate` and `errorPatterns`

**Progress:**
- `getVocabSetProgress(vocabSetId)`: GET progress stats for vocab set
- `getOverallProgress()`: GET user's overall statistics
- `getSessionHistory(limit)`: GET recent practice sessions

**League:**
- `createLeague(name, scoreMode)`: POST to create a league (teacher only)
- `joinLeague(joinCode)`: POST to join a league with 6-char code
- `getLeague(leagueId)`: GET league details
- `getLeaderboard(leagueId)`: GET league leaderboard
- `getMembers(leagueId)`: GET league members (teacher only)
- `updateLeague(leagueId, data)`: PUT to update score mode, assigned vocab sets, etc.
- `removeMember(leagueId, userId)`: DELETE member from league

**User:**
- `getProfile()`: GET `/users/profile` to fetch user profile (displayName, etc.)
- `updateProfile(data)`: PUT `/users/profile` to update display name
- `inviteUser(data)`: POST `/users/invite` to onboard a new user without league assignment (teacher only)
- `inviteToLeague(leagueId, data)`: POST `/league/{leagueId}/invite` to create user and immediately add to league (teacher only)

**TTS (Text-to-Speech):**
- `getTtsVoices()`: GET `/tts/voices` — list available Polly voices per language
- `synthesizeSpeech(text, languageCode, voiceId)`: POST `/tts/synthesize` — returns presigned MP3 URL (cached in S3)

**Learning Goals:**
- `getGoals()`: GET `/goals` — list user's learning goals
- `createGoal(data)`: POST `/goals` — create goal with deadline and target mastery level
- `getGoal(goalId)`: GET `/goals/{goalId}` — goal details + progress/pace/status
- `updateGoal(goalId, data)`: PUT `/goals/{goalId}` — update goal parameters
- `deleteGoal(goalId)`: DELETE `/goals/{goalId}` — remove goal
- `getGoalMembers(goalId)`: GET `/goals/{goalId}/members` — league member progress for teacher's league-wide goal

### services/storage.js

Client-side storage utilities for caching and offline capability.

**Functions:**
- `saveToCache(key, data, ttl)`: Save data to localStorage with expiry
- `getFromCache(key)`: Retrieve cached data if not expired
- `clearCache(key)`: Remove specific cache entry
- `clearAllCache()`: Clear all app cache

### services/tts.js

Text-to-speech service wrapping the Amazon Polly backend (`GET /tts/voices`, `POST /tts/synthesize`). Only the **target-language word** is synthesized (never the German source word).

**Key Functions:**
- `getVoices(languageCode)`: Fetch available Polly voices for a given language code. Results are cached for the session.
- `synthesize(text, languageCode, voiceId)`: POST to backend, returns a presigned S3 MP3 URL. The backend caches MP3s in S3 and rate-limits via the TtsUsage table.
- `pronounceWithStoredVoice(text, languageCode)`: Convenience wrapper that reads the stored voice preference from localStorage (`vocab_trainer_tts_voice_{languageCode}`), calls `synthesize`, and plays the audio.

**State / Persistence:**
- Selected voice and accent per language are persisted to localStorage (key `vocab_trainer_tts_voice_{languageCode}`).
- Available voices are cached in-memory for the current session to avoid redundant API calls.

**Implementation Notes:**
- The backend MP3 cache means repeated requests for the same word/voice are served instantly from S3.
- New vocabulary words shown during practice are automatically pronounced when the user has TTS enabled.

## State Management (Pinia Stores)

### stores/auth.js

**State:**
- `user`: Object with user profile (email, displayName, userId)
- `accessToken`: String
- `idToken`: String
- `refreshToken`: String
- `displayName`: String or null — display name loaded from `GET /users/profile` and persisted to localStorage (`vocab_trainer_displayName`)
- `isLoading`: Boolean for auth checks
- `error`: String or null
- `role`: String — `'student'` or `'teacher'` (extracted from `cognito:groups` claim in ID token, persisted to localStorage)
- `leagueId`: String or null (persisted to localStorage)

**Computed:**
- `isAuthenticated`: Boolean — true when accessToken and user both exist

**Actions:**
- `login()`: Initiate Cognito OAuth flow
- `handleAuthCallback(code)`: Process OAuth callback, extract role from token, persist tokens
- `logout()`: Clear all auth state including role, leagueId, and displayName from localStorage, redirect to Cognito logout
- `refreshSession()`: Refresh tokens using refresh token
- `loadUserFromStorage()`: Restore session on page load, extract role from stored ID token
- `loadProfile()`: Fetch user profile from `GET /users/profile`; updates `displayName` state and persists to localStorage
- `checkTokenExpiry()`: Validates token freshness, auto-refreshes if within 5 minutes of expiry
- `setLeagueId(id)`: Set/clear league ID (persisted to localStorage)
- `setRole(newRole)`: Override role (persisted to localStorage)

**Internal:**
- `_extractRoleFromToken(idToken)`: Decodes JWT payload, checks `cognito:groups` for `'teachers'` group, defaults to `'student'`
- `persistTokens()`: Syncs all token and user state to localStorage

### stores/vocab.js

**State:**
- `vocabSets`: Array of all vocab sets
- `currentVocabSet`: Currently selected/viewed vocab set
- `isLoading`: Loading state
- `error`: Error message

**Getters:**
- `sortedVocabSets`: Vocab sets sorted by creation date (newest first)
- `vocabSetById`: Function that returns vocab set by ID

**Actions:**
- `fetchVocabSets()`: Load all vocab sets
- `fetchVocabSet(id)`: Load single vocab set with items
- `createVocabSet(data)`: Create new vocab set
- `updateVocabSet(id, data)`: Update existing vocab set
- `deleteVocabSet(id)`: Delete vocab set
- `setCurrentVocabSet(id)`: Set active vocab set

### stores/practice.js

**State:**
- `currentSession`: Object with session data (`sessionId`, `vocabSetId`, `direction`, `startTime`)
- `questions`: Array of questions for current session (populated from backend, which applies smart repetition — weak words are prioritized)
- `currentQuestionIndex`: Integer
- `answers`: Array of answer records
- `sessionResults`: Object with score, detailed results, `leagueUpdate`, and `errorPatterns` from API
- `isSessionActive`: Boolean
- `currentStreak`: Integer — consecutive correct answers in current session

**Getters:**
- `currentQuestion`: Returns current question object
- `progress`: Returns `{current, total, percentage}` for progress bar
- `score`: Returns `{correct, total, percentage}`

**Actions:**
- `startSession(vocabSetId, options)`: POST to backend, populate questions array. Backend handles smart repetition (weak words prioritized).
- `submitAnswer(answer)`: Check answer locally using `checkAnswer` from fuzzyMatch. Returns result with `'exact'`, `'close'`, or `'wrong'`. Pushes answer record.
- `acceptCloseAnswer()`: Mark last close answer as correct, increment streak
- `rejectCloseAnswer()`: Mark last close answer as incorrect, reset streak
- `nextQuestion()`: Move to next question
- `skipQuestion()`: Remove current question and re-append at end of queue (will be asked again)
- `endSession()`: POST results to backend. Captures `leagueUpdate` and `errorPatterns` from response into `sessionResults`.
- `resetSession()`: Clear all session state

**Answer Record Structure:**
```javascript
{
  questionId: 'string',
  itemId: 'string',
  userAnswer: 'string',
  correctAnswer: 'string',
  result: 'exact' | 'close' | 'wrong',
  correct: Boolean, // updated if user accepts/rejects 'close'
  timestamp: Number
}
```

**Note:** No phonetics stripping is performed in the practice store. Answer normalization is handled by `checkAnswer` in `utils/fuzzyMatch.js`.

### stores/ui.js

**State:**
- `toasts`: Array of toast notifications
- `modal`: Object with modal state {isOpen, component, props}
- `sidebarOpen`: Boolean for responsive sidebar

**Actions:**
- `showToast(message, type, duration)`: Add toast notification
- `removeToast(id)`: Remove toast by ID
- `openModal(component, props)`: Open modal with component
- `closeModal()`: Close modal
- `toggleSidebar()`: Toggle sidebar state

## Composables

### composables/useAuth.js

Composition function that wraps auth store for component use.

**Returns:**
- `user`: Reactive user object
- `isAuthenticated`: Reactive auth status
- `isLoading`: Boolean
- `error`: Error string
- `userName`: Computed — prioritizes `localStorage.getItem('vocab_trainer_displayName')`, falls back to `user.name`, then empty string
- `userInitials`: Computed — first letters of userName, uppercase, max 2 chars
- `login()`: Login function
- `logout()`: Logout function
- `handleCallback(code)`: Process OAuth callback
- `checkAuth()`: Load user from storage

### composables/useApi.js

Generic API request composable with loading/error states.

**Usage Pattern:**
```javascript
const { data, isLoading, error, execute } = useApi(() => api.getVocabSets())
```

**Returns:**
- `data`: Reactive data from API
- `isLoading`: Boolean loading state
- `error`: Error object if request fails
- `execute()`: Function to trigger request

### composables/useUpload.js

Handles multi-image upload flow including S3 presigned URLs and direct upload.

**Returns:**
- `uploadProgress`: Number 0-100
- `isUploading`: Boolean
- `error`: Error message
- `filesProgress`: Ref to array of per-file progress objects (`{name, progress, status}`)
- `uploadMultipleImages(files, targetLanguage)`: Async function that uploads multiple files, returns `{vocabSetId, imageKeys}`
- `triggerExtraction(vocabSetId, imageKey)`: Trigger extraction for one image
- `pollExtractionStatus(vocabSetId)`: Poll until extraction completes
- `reset()`: Reset upload state

### composables/usePractice.js

Practice session logic and answer validation.

**Returns:**
- `checkAnswer(userAnswer, correctAnswer)`: Returns result using fuzzy matching
- `calculateScore(answers)`: Return score object
- `formatFeedback(isCorrect, correctAnswer)`: Format feedback message

**Fuzzy Matching Rules:**
- Ignore case differences
- Trim whitespace
- Accept answers within 1-2 character edit distance for words >5 chars
- Handle common typos (double letters, transpositions)
- Three-tier result: `'exact'`, `'close'`, `'wrong'`

### composables/useToast.js

Toast notification wrapper for UI store.

**Returns:**
- `showSuccess(message)`: Show success toast
- `showError(message)`: Show error toast
- `showInfo(message)`: Show info toast
- `showWarning(message)`: Show warning toast

## Key Components

### components/common/AppHeader.vue

Application header with navigation, dark mode toggle, display name editor, and help link.

**Features:**
- VocabGym logo/brand with 💪 emoji
- Desktop navigation links: Dashboard, Hochladen, Fortschritt, Liga
- Help icon link (question mark SVG) linking to /help
- Dark mode toggle button (🌙/☀️)
- Display name editor (inline popup):
  - Click username to open editor popup
  - Text input with save/cancel buttons
  - Saves to API via `PUT /users/profile` and `localStorage.setItem('vocab_trainer_displayName')`
- Logout button
- Mobile hamburger menu with all nav links including Liga and Hilfe

**Dark Mode:**
- Reads preference from `localStorage.getItem('vocabgym_dark_mode')` or system `prefers-color-scheme`
- Toggles `dark` class on `document.documentElement`
- Persists preference to localStorage

**Implementation Notes:**
- Uses `useAuth` composable for `isAuthenticated` and `userName`
- All text in German (Hochladen, Fortschritt, Liga, Hilfe, etc.)

### components/common/AppFooter.vue

Global application footer rendered on every page.

**Features:**
- Navigation links: Datenschutz (`/datenschutz`), Impressum (`/impressum`), Hilfe (`/help`)
- Logo attribution: "Logo © Alexa Binnewies" — the logo `frontend/public/logo.svg` is copyright Alexa Binnewies and is **not** covered by the project's GPL license
- Dark mode support

**Implementation Notes:**
- Included once in `App.vue`, displayed below all page content
- All links are plain `<router-link>` elements pointing to public (no-auth) routes

### components/upload/ImageDropzone.vue

Multi-image drag-and-drop file upload component with file validation.

**Features:**
- Drag-and-drop zone with hover states
- Click to browse file picker
- **Multi-file support**: Select and preview multiple images, add more after initial selection
- Per-image preview thumbnails with remove button
- File type validation: JPG and PNG only (HEIC not supported)
- File size validation (max 10MB per image)
- "Upload" button triggers upload for all selected files
- Dark mode support for all states

**Props:**
- `vocabSetId`: String (optional, for adding images to existing set)

**Events:**
- `@files-selected`: Emitted with files array when selection changes
- `@upload-success`: Emitted with `{files, vocabSetId}` when user clicks upload
- `@upload-error`: Emitted with error message

**Implementation Notes:**
- Uses `isValidFileType` and `isValidFileSize` from `utils/validators.js`
- `ALLOWED_IMAGE_TYPES` = `['image/jpeg', 'image/png']` — no HEIC
- Hidden file input with `accept="image/jpeg,image/png"` and `multiple` attribute
- FileReader for image previews
- Exposes `clearAll()` method via `defineExpose`

### components/review/VocabTable.vue

Editable table for reviewing extracted vocabulary.

**Features:**
- Editable source (Deutsch) and target columns
- Column header shows target language name dynamically
- Add/remove rows per image group
- Validation indicators (empty fields highlighted with red border)
- Inline editing with input fields using `.input-field` class

**Props:**
- `vocabSet`: Object with vocabSetId and items array
- `isEditable`: Boolean (default: true)

**Events:**
- `@save`: Emitted with updated vocab set data
- `@cancel`: Emitted when user cancels review

**Data Structure for Items:**
```javascript
{
  itemId: 'uuid',
  source: 'das Haus',   // German (source language)
  target: 'la maison',  // Target language
  notes: '',
  order: 1
}
```

**Note:** Legacy `german`/`french` fields are still read for backward compatibility. The review view reads `item.source || item.german` and `item.target || item.french`.

### components/practice/QuestionCard.vue

Main practice interface showing question and answer input.

**Features:**
- Large, clear question text
- Text input field for answer
- "Check" button (also triggered by Enter key)
- Three-tier feedback: exact (correct), close (user decides), wrong (incorrect)
- Correct answer display when wrong
- Streak counter display
- Skip button (moves question to end of queue)

**Props:**
- `question`: Object with question data
- `direction`: String (`'source-target'` or `'target-source'`)
- `feedback`: Object with feedback state
- `streak`: Number — current streak count
- `hintEnabled`: Boolean — enable hints after streak ≥ 2
- `targetLanguage`: String — language code for display

**Events:**
- `@submit`: Emitted with user answer
- `@skip`: Emitted to skip question
- `@next`: Emitted to move to next question
- `@accept-close`: Emitted when user accepts a close match
- `@reject-close`: Emitted when user rejects a close match

### components/practice/SessionSummary.vue

End-of-session results display with statistics, league update, and error pattern analysis.

**Features:**
- Score display (percentage, X/Y correct)
- Duration display
- **League update card**: Shows points earned and current streak (when `results.leagueUpdate` is present)
- **Lernhinweis (error pattern analysis) card**: Yellow card with 💡 icon showing:
  - `errorPatterns.summary`: Text summary of common mistakes
  - `errorPatterns.articleErrors`: List of article mistakes with strikethrough wrong → correct
  - `errorPatterns.repeatedErrors`: List of words the user repeatedly gets wrong with count
- Detailed results list with correct/incorrect highlighting
- "Nochmal üben" and "Zum Dashboard" action buttons

**Props:**
- `results`: Object with `{score, duration, detailedResults, leagueUpdate, errorPatterns}`

**Events:**
- `@practice-again`: Restart practice
- `@back`: Navigate to dashboard

### components/practice/PronounceButton.vue

Button that synthesizes and plays the target-language pronunciation of a word via Amazon Polly.

**Features:**
- Speaker icon button (🔊) placed next to the target-language word in practice and review
- On click: calls `tts.pronounceWithStoredVoice(text, languageCode)` and plays the returned MP3 via the browser Audio API
- Shows loading state while synthesis request is in flight
- Displays an error toast if the rate limit is reached or synthesis fails

**Props:**
- `text`: String — the target-language word to pronounce
- `languageCode`: String — language code (e.g. `'fr'`, `'en'`)
- `autoPlay`: Boolean (default: false) — if true, pronounces automatically on mount (used for new words in practice)

**Implementation Notes:**
- Voice preference read from localStorage key `vocab_trainer_tts_voice_{languageCode}`; falls back to the first available voice for the language
- Only the target-language word is synthesized, never the German source word
- `aria-label="Aussprache anhören"` for accessibility

### components/dashboard/VocabSetCard.vue

Card component displaying vocab set summary on dashboard.

**Features:**
- Title and metadata (chapter, items count)
- Thumbnail of source image
- Progress indicator (mastery percentage)
- Last practiced date
- Quick action buttons (Practice, View, Delete)

**Props:**
- `vocabSet`: Object with complete vocab set data

**Events:**
- `@practice`: Emitted to start practice
- `@view`: Emitted to view details
- `@delete`: Emitted to delete vocab set

### components/dashboard/GoalBanner.vue

Banner component displayed at the top of the Dashboard showing the nearest active Lernziel.

**Features:**
- Displays goal title, target mastery level, deadline, and current status
- Status badge with color coding: `on-track` (green), `at-risk` (yellow), `behind` (red), `achieved` (blue), `expired` (gray)
- Progress bar showing current mastery vs. target mastery
- Link to full goal management view
- Hidden when no active goals exist

**Props:**
- `goal`: Object with goal data (`title`, `deadline`, `targetMasteryLevel`, `status`, `currentMastery`)

**Implementation Notes:**
- Loaded in DashboardView.vue via `getGoals()` API call; nearest active goal selected by earliest deadline
- All text in German

### components/progress/ProgressChart.vue

Chart component showing progress over time.

**Features:**
- Line chart of practice sessions over time
- Bar chart of mastery by vocab set
- Filterable by date range

**Props:**
- `data`: Array of session data
- `type`: String ('line' or 'bar')

**Implementation Notes:**
- Use Chart.js with vue-chartjs wrapper
- Format dates for x-axis labels
- Color code by accuracy (red < 50%, yellow 50-80%, green > 80%)
- Responsive chart sizing

## Views

### views/LandingView.vue

Landing page for unauthenticated users.

**Features:**
- Hero section with app description (in German)
- Key features overview (scan, review, practice)
- Multi-language support mentioned
- "Jetzt starten" button → login

**Implementation:**
- Check auth on mount → redirect to dashboard if authenticated
- All text in German
- Dark mode support

### views/DashboardView.vue

Main dashboard after login.

**Features:**
- Welcome message with user name
- GoalBanner: shows the nearest active Lernziel with its status and deadline (if a goal is set)
- Stats overview (total vocab sets, total words)
- Grid of vocab set cards
- "Hochladen" button for new uploads
- League vocab sets section (if user has a league)
- **Teacher-only**: "Nutzer einladen" section to onboard new students by email via `POST /users/invite` (without league) or via the league invite flow

**Implementation:**
- Fetch vocab sets on mount
- Use VocabSetCard component in grid
- Responsive grid (1 col mobile, 2 col tablet, 3+ col desktop)
- Handle empty state (no vocab sets yet)
- All text in German

### views/UploadView.vue

Multi-image upload and extraction flow.

**Features:**
- **Target language selector**: Dropdown with all supported languages from `SUPPORTED_LANGUAGES`
- ImageDropzone component (multi-file support)
- Per-file upload progress display with status indicators (✓ done, ✗ error, uploading percentage)
- Extraction status polling after upload
- Auto-redirect to ReviewView when complete

**Implementation:**
- Uses `useUpload` composable with `uploadMultipleImages(files, targetLanguage)`
- Three phases: `'select'` → `'processing'`
- After all images uploaded, triggers extraction per image sequentially
- Polls extraction status per image
- Shows success toast with file count
- Error display with retry button
- All text in German

### views/ReviewView.vue

Review and edit extracted vocabulary with vertical layout and per-image grouping.

**Features:**
- MetadataForm for title, chapter, page number, topic
- **Per-image grouping**: Items grouped by source image, each group shows:
  - Image preview (lazy loaded, max height 96)
  - "Seite N" heading
  - Editable table with columns: #, Deutsch, [Target Language Name], delete button
- Inline editing with `.input-field` inputs
- Delete per row (button visible on hover via `group-hover:opacity-100`)
- Add row button per image group ("+ Eintrag hinzufügen")
- "Speichern & Freigeben" and "Abbrechen" buttons in header
- Validation: empty source/target fields highlighted with red border

**Implementation:**
- Vertical layout (not side-by-side)
- Reads `item.source || item.german` and `item.target || item.french` for backward compatibility
- Updates items via `updateItem(item, 'source'|'target', value)` function
- Target language name shown in column header from `getLanguageName()`
- All text in German

### views/PracticeView.vue

Practice session interface.

**Features:**
- Direction selector: "Deutsch → [Target Language]" or "[Target Language] → Deutsch" using `getLanguageName()`
- QuestionCard component with streak and hint support
- Progress bar at top
- Three-tier answer feedback (exact, close, wrong)
- Exit confirmation if session incomplete (German confirm dialog)
- SessionSummary with league update and error patterns on completion

**Implementation:**
- Maps `source-target`/`target-source` directions to legacy `de-fr`/`fr-de` for backend API compatibility
- Loads vocab set metadata to get `targetLanguage` code
- Backend handles smart repetition (weak words prioritized in returned questions)
- `onBeforeRouteLeave` guard saves partial progress
- All text in German

### views/ProgressView.vue

Overall progress and statistics view.

**Features:**
- Overall stats (total words learned, accuracy rate, practice time)
- Progress chart (sessions over time)
- Mastery breakdown by vocab set
- Session history table

**Implementation:**
- Fetch progress data on mount
- Use ProgressChart component
- Table with sortable columns
- Date range filter for charts

### views/VocabSetDetailView.vue

Detailed view of single vocab set.

**Features:**
- Full vocabulary list (read-only table with source/target columns)
- Edit button → ReviewView
- Practice button → PracticeView
- Delete button with confirmation
- Stats for this vocab set (times practiced, average score)

**Implementation:**
- Fetch vocab set by ID
- Show all items in scrollable table
- Action buttons at top

### views/LeagueView.vue

League management with three states based on user role and league membership.

**State 1 — Student without league (join form):**
- Title: "Liga beitreten"
- Explanation text (Du-Form)
- 6-character join code input (uppercase, monospace, centered)
- "Beitreten" button
- Error display for invalid codes

**State 2 — Teacher without league (create form):**
- Title: "Liga erstellen"
- Explanation text (Sie-Form)
- Name input (e.g., "Klasse 9b Englisch")
- Score mode selector (Gesamtzahl Richtige, Wöchentlich, Genauigkeit, Kombiniert)
- "Liga erstellen" button
- Error display

**State 3 — User with league (dashboard):**
- League name header with participant count and score mode
- Own stats banner (rank, score, streak)
- Leaderboard table (Rang, Name, Score, 🔥 Streak)
- "Jetzt üben" section: grid of assigned league vocab sets with practice links
- **Teacher-only management section:**
  - Join code display with copy button
  - Score mode editor
  - Vocab set assignment (checkboxes of teacher's own sets)
  - Member management with expandable details (stats, last practice, remove button)

**Implementation:**
- Uses `authStore.leagueId` and `authStore.role` for state determination
- Loads league data, leaderboard, members, and vocab sets on mount
- Clears stored leagueId on 404/403 responses
- All text in German

### views/LeagueJoinView.vue

Separate league join view accessible via `/league/join/:code?`.

**Features:**
- Join code input pre-populated from route params
- Join league API call
- Redirect to League view on success

### views/HelpView.vue

Help and documentation page with role-based tabs.

**Features:**
- Tab navigation: "🎓 Für Trainierende" (student) and "👩‍🏫 Für Lehrende" (teacher)
- **Student tab** (Du-Form):
  - Welcome section
  - Step-by-step guide: Anmelden & Namen setzen, Liga beitreten, Üben, Punkte sammeln & Streak halten
  - Tips: Tippfehler handling, Artikel importance
  - Multi-language mention (Französisch, Englisch, Spanisch, Italienisch)
- **Teacher tab** (Sie-Form):
  - Account setup guide
  - Liga creation and management
  - Vocab set upload and assignment workflow
  - Student management

**Implementation:**
- `activeTab` state toggles between `'student'` and `'teacher'`
- Custom prose styling classes (`.section-title`, `.step`, `.tip-card`, etc.)
- All content in German
- Does not require authentication (`meta.requiresAuth: false`)

### views/CallbackView.vue

OAuth callback handler for Cognito authentication flow.

### views/PrivacyView.vue

Datenschutzerklärung (privacy policy) page — publicly accessible without login.

**Features:**
- Full privacy policy in German
- Accessible at `/datenschutz`
- No authentication required (`meta.requiresAuth: false`)
- Linked from AppFooter on every page

### views/ImpressumView.vue

Impressum page — publicly accessible without login.

**Features:**
- Legal imprint in German
- Accessible at `/impressum`
- No authentication required (`meta.requiresAuth: false`)
- Linked from AppFooter on every page

### views/NotFoundView.vue

404 page with link back to dashboard.

## Routing Configuration

### router/index.js

Vue Router setup with route guards. All route titles are in German.

**Routes:**
```javascript
[
  { path: '/', name: 'Landing', meta: { requiresAuth: false, title: 'Willkommen' } },
  { path: '/callback', name: 'Callback', meta: { requiresAuth: false, title: 'Anmeldung...' } },
  { path: '/dashboard', name: 'Dashboard', meta: { requiresAuth: true, title: 'Dashboard' } },
  { path: '/upload', name: 'Upload', meta: { requiresAuth: true, title: 'Bild hochladen' } },
  { path: '/review/:vocabSetId', name: 'Review', meta: { requiresAuth: true, title: 'Vokabeln prüfen' }, props: true },
  { path: '/practice/:vocabSetId', name: 'Practice', meta: { requiresAuth: true, title: 'Üben' }, props: true },
  { path: '/progress', name: 'Progress', meta: { requiresAuth: true, title: 'Fortschritt' } },
  { path: '/vocab/:vocabSetId', name: 'VocabSetDetail', meta: { requiresAuth: true, title: 'Vokabelset' }, props: true },
  { path: '/league', name: 'League', meta: { requiresAuth: true, title: 'Liga' } },
  { path: '/league/join/:code?', name: 'LeagueJoin', meta: { requiresAuth: true, title: 'Liga beitreten' }, props: true },
  { path: '/help', name: 'Help', meta: { requiresAuth: false, title: 'Hilfe' } },
  { path: '/datenschutz', name: 'Privacy', meta: { requiresAuth: false, title: 'Datenschutz' } },
  { path: '/impressum', name: 'Impressum', meta: { requiresAuth: false, title: 'Impressum' } },
  { path: '/:pathMatch(.*)*', name: 'NotFound', meta: { requiresAuth: false, title: 'Nicht gefunden' } }
]
```

**Navigation Guards:**
- Global `beforeEach` guard: Check `meta.requiresAuth`
- Updates `document.title` to `"${title} - VocabTrainer"`
- If requires auth and not authenticated: call `authStore.login()` (redirect to Cognito)
- If authenticated and on landing: redirect to dashboard
- All views except Landing are lazy-loaded with `() => import()`

## Styling Guidelines

### Dark Mode

Full dark mode support using Tailwind's `dark:` variant. Dark mode is toggled via AppHeader and persisted to `localStorage.getItem('vocabgym_dark_mode')`. Falls back to system `prefers-color-scheme` on first visit.

**Global dark mode styles** in `src/assets/styles/main.css`:
- Body: `dark:text-gray-100 dark:bg-gray-900`
- All form inputs (`input[type="text"]`, `select`, `textarea`, etc.): `dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100 dark:placeholder-gray-400`

### Typography & Fonts

The Inter font is **self-hosted** via `@font-face` declarations in `src/assets/styles/main.css`. No Google Fonts dependency — font files are bundled with the frontend and served from S3/CloudFront. This ensures privacy compliance and offline reliability.

### Utility Classes (main.css `@layer components`)

- `.btn` — Base button: inline-flex, centered, rounded-md, focus ring with dark offset
- `.btn-primary` — Primary blue button with dark-compatible focus ring
- `.btn-secondary` — Gray button: `dark:bg-gray-700 dark:text-gray-100 dark:hover:bg-gray-600`
- `.btn-danger` — Red error button
- `.btn-success` — Green success button
- `.card` — White card: `dark:bg-gray-800 dark:shadow-gray-900/30`
- `.input-field` — Form input for use inside forms (no explicit border): `dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100`
- `.input` — Standalone input with explicit border: `dark:bg-gray-700 dark:border-gray-600 dark:text-gray-100`
- `.label` — Form label: `dark:text-gray-300`

### Tailwind Configuration

**Theme Extensions:**
```javascript
{
  colors: {
    primary: {
      50: '#f0f9ff',
      100: '#e0f2fe',
      // ... (blue scale)
      900: '#0c4a6e',
    },
    success: '#10b981',
    error: '#ef4444',
    warning: '#f59e0b',
    info: '#3b82f6'
  },
  fontFamily: {
    sans: ['Inter', 'system-ui', 'sans-serif'],
  }
}
```

**Design System:**
- **Spacing**: Use Tailwind's default scale (4px increments)
- **Typography**: Base 16px, scale up for headings (h1-h4 styled in `@layer base`)
- **Radius**: Consistent border-radius (rounded-lg for cards, rounded-md for inputs)
- **Shadows**: Subtle shadows (shadow-sm, shadow-md)
- **Transitions**: Use transition-all duration-200 for interactive elements
- **Dark mode**: All components use `dark:` variants for backgrounds, text, borders

### Responsive Design

- **Breakpoints**: Use Tailwind defaults (sm: 640px, md: 768px, lg: 1024px, xl: 1280px)
- **Mobile-first**: Design for mobile, enhance for larger screens
- **Touch targets**: Minimum 44x44px for buttons on mobile
- **Desktop nav**: Horizontal with full links; mobile nav: hamburger menu with slide-down
- **Content max-width**: `max-w-7xl` for header, `max-w-4xl` for content views, `max-w-2xl` for practice

## Form Validation

### Validation Rules

**Upload:**
- File type: Must be image/jpeg or image/png (HEIC not supported)
- File size: Maximum 10MB per file
- Required: At least one file selected

**Review:**
- Source field: Required, 1-100 characters
- Target field: Required, 1-100 characters
- Chapter: Optional, max 50 characters
- Page: Optional, must be positive integer
- Topic: Optional, max 100 characters

**Practice:**
- Answer: Required (cannot submit empty)

**League Join:**
- Join code: Required, 6 characters

### Validation Implementation

Custom validation utilities in `utils/validators.js`. All messages in German:

```javascript
export const required = (value) => !!value || 'Dieses Feld ist erforderlich'
export const maxLength = (max) => (value) =>
  !value || value.length <= max || `Maximal ${max} Zeichen erlaubt`
export const minLength = (min) => (value) =>
  !value || value.length >= min || `Mindestens ${min} Zeichen erforderlich`
export const isPositiveInteger = (value) =>
  !value || (Number.isInteger(Number(value)) && Number(value) > 0) || 'Muss eine positive Ganzzahl sein'
export function isValidFileType(file) // checks against ['image/jpeg', 'image/png']
export function isValidFileSize(file, maxSize) // default 10MB
```

Display validation errors inline below fields with red text.

## Error Handling

### Error Types and Responses

All error messages are in German.

**Network Errors:**
- Show toast: "Verbindungsproblem. Bitte Internetverbindung prüfen."
- Retry button for failed requests

**Authentication Errors (401):**
- Clear tokens
- Redirect to landing page with message: "Sitzung abgelaufen. Bitte erneut anmelden."

**Authorization Errors (403):**
- Show toast: "Keine Berechtigung für diese Aktion."
- Redirect to dashboard

**Validation Errors (400):**
- Display field-specific errors from API response
- Highlight invalid fields

**Server Errors (500):**
- Show toast: "Etwas ist schiefgegangen. Bitte erneut versuchen."
- Log error details to console

**Not Found (404):**
- Show "Nicht gefunden" message
- Provide link back to dashboard

### Error Boundaries

Implement global error handler in App.vue to catch uncaught errors:
```javascript
app.config.errorHandler = (err, instance, info) => {
  console.error('Global error:', err, info)
  // Show generic error toast
}
```

## Performance Optimization

### Code Splitting

- All routes except Landing are lazy-loaded: `component: () => import('./views/DashboardView.vue')`
- Lazy load heavy components (Chart.js) only when needed
- Dynamic imports for large libraries

### Image Optimization

- Use lazy loading for vocab set thumbnails and review images: `loading="lazy"`
- Serve responsive images from S3 with CloudFront
- Client-side previews via FileReader

### API Optimization

- Implement request caching in storage.js (short TTL for list endpoints)
- Debounce search/filter inputs (300ms delay)
- Paginate vocab set lists if count grows large

### Bundle Size

- Tree-shake unused Tailwind classes with purge configuration (`content` in tailwind.config.js)
- Minimize dependencies (check bundle analyzer)

## Testing Strategy

### Unit Tests (Vitest)

**Priority Components:**
- Validators (utils/validators.js) — German error messages
- Fuzzy matching logic (utils/fuzzyMatch.js) — three-tier results
- Language utilities (utils/languages.js)
- Composables (useApi, usePractice, useAuth)
- Pinia stores (actions and getters)

**Example Test Pattern:**
```javascript
describe('fuzzyMatch', () => {
  it('should return exact for matching strings', () => {
    expect(checkAnswer('la maison', 'la maison')).toBe('exact')
  })

  it('should return close for minor typos', () => {
    expect(checkAnswer('la maisom', 'la maison')).toBe('close')
  })

  it('should return wrong for completely different strings', () => {
    expect(checkAnswer('le chat', 'la maison')).toBe('wrong')
  })
})
```

### Component Tests (Vue Test Utils)

**Priority Components:**
- QuestionCard.vue (answer submission, three-tier feedback, accept/reject close)
- VocabTable.vue (editing, adding/removing rows with source/target fields)
- ImageDropzone.vue (multi-file validation, upload trigger)
- SessionSummary.vue (league update display, error pattern rendering)
- AppHeader.vue (display name editor, dark mode toggle)

### E2E Tests (Playwright)

**Critical User Flows:**
1. Authentication: Login → Dashboard → Logout
2. Upload: Login → Select language → Upload multiple images → Review → Save → Dashboard
3. Practice: Login → Select vocab set → Complete session → View summary with error patterns
4. League: Teacher creates league → Student joins → Practice → Check leaderboard

**Test Environment:**
- Use staging environment with test Cognito user pool
- Mock S3 uploads and Textract responses
- Reset test database between runs

## Accessibility (a11y)

### Requirements

- **Keyboard Navigation**: All interactive elements accessible via keyboard (Tab, Enter, Esc)
- **Screen Reader Support**: Proper ARIA labels, landmarks, and announcements
- **Color Contrast**: WCAG AA compliance (4.5:1 for normal text) — verified in both light and dark modes
- **Focus Indicators**: Clear focus outlines on all interactive elements (Tailwind `focus:ring-2`)
- **Alt Text**: All images have descriptive alt attributes

### Implementation Checklist

- Use semantic HTML (button, nav, main, article)
- Add `role` attributes where semantic HTML insufficient
- Use `aria-label` for icon buttons (e.g., "Hilfe", "Heller Modus"/"Dunkler Modus", "Menü öffnen", "Zeile löschen")
- Announce dynamic content changes with `aria-live` regions
- Test with keyboard only (no mouse)
- Test with screen reader (VoiceOver on Mac)

**Example Patterns:**
```vue
<!-- Help link in header -->
<router-link to="/help" title="Hilfe" aria-label="Hilfe">
  <svg>...</svg>
</router-link>

<!-- Dark mode toggle -->
<button :aria-label="isDark ? 'Heller Modus' : 'Dunkler Modus'">
  {{ isDark ? '☀️' : '🌙' }}
</button>

<!-- Delete row button -->
<button aria-label="Zeile löschen" @click="deleteItem(item)">
  <svg>...</svg>
</button>
```

## Deployment

### Build Process

1. **Install dependencies**: `npm install`
2. **Run linter**: `npm run lint` (ESLint + Prettier)
3. **Run tests**: `npm run test`
4. **Build for production**: `npm run build`
   - Output to `dist/` directory
   - Minified and optimized
   - Environment variables injected from .env.production

### S3 Deployment

**S3 Bucket Configuration:**
- Enable static website hosting
- Set index document: `index.html`
- Set error document: `index.html` (for SPA routing)
- Bucket policy: Allow CloudFront access only

**Upload Process:**
```bash
aws s3 sync dist/ s3://vocab-trainer-frontend --delete
```

**CloudFront Configuration:**
- Origin: S3 bucket website endpoint
- Default root object: `index.html`
- Custom error responses: 403, 404 → /index.html (HTTP 200) for SPA routing
- HTTPS only with TLS 1.2+
- Compress objects: Enabled (gzip/brotli)
