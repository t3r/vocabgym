# Vue Frontend Implementation Guide

## Project Context

This is the frontend implementation guide for **VocabTrainer**, a web-based French vocabulary training application for 9th grade German Gymnasium students. The application allows students to scan workbook pages, extract vocabulary automatically using AI, review and edit the extracted content, and practice with typing-based exercises.

## Technology Stack

- **Framework**: Vue 3 with Composition API
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: Pinia
- **Routing**: Vue Router
- **HTTP Client**: Axios
- **Charts**: Chart.js with vue-chartjs wrapper
- **Authentication**: AWS Cognito (OAuth2 flow with hosted UI)

## Architecture Overview

The frontend is a single-page application (SPA) that communicates with a serverless backend via REST API (AWS API Gateway + Lambda). It is deployed as a static site on S3 and served through CloudFront CDN.

### Key User Flows

1. **Authentication Flow**: User clicks login → redirected to Cognito hosted UI → OAuth callback → token stored → redirect to dashboard
2. **Upload Flow**: User drags/drops workbook image → presigned URL requested → direct upload to S3 → trigger extraction → poll for results
3. **Review Flow**: Extraction complete → display editable table → user approves/edits → save to backend
4. **Practice Flow**: User selects vocab set → questions loaded → type answer → immediate feedback → session summary

## Project Structure

```
vocab-trainer-frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── assets/
│   │   └── logo.svg
│   ├── components/
│   │   ├── auth/
│   │   │   ├── LoginButton.vue
│   │   │   └── LogoutButton.vue
│   │   ├── common/
│   │   │   ├── AppHeader.vue
│   │   │   ├── LoadingSpinner.vue
│   │   │   ├── Modal.vue
│   │   │   └── Toast.vue
│   │   ├── dashboard/
│   │   │   ├── VocabSetCard.vue
│   │   │   ├── StatsOverview.vue
│   │   │   └── RecentSessions.vue
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
│   │   │   └── SessionSummary.vue
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
│   │   └── storage.js
│   ├── utils/
│   │   ├── validators.js
│   │   ├── formatters.js
│   │   └── fuzzyMatch.js
│   ├── views/
│   │   ├── LandingView.vue
│   │   ├── DashboardView.vue
│   │   ├── UploadView.vue
│   │   ├── ReviewView.vue
│   │   ├── PracticeView.vue
│   │   ├── ProgressView.vue
│   │   └── VocabSetDetailView.vue
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
- `startPracticeSession(vocabSetId, options)`: POST to create session
- `submitAnswer(sessionId, questionId, answer)`: POST answer, get feedback
- `completeSession(sessionId)`: POST to finalize session

**Progress:**
- `getVocabSetProgress(vocabSetId)`: GET progress stats for vocab set
- `getOverallProgress()`: GET user's overall statistics
- `getSessionHistory(limit)`: GET recent practice sessions

### services/storage.js

Client-side storage utilities for caching and offline capability.

**Functions:**
- `saveToCache(key, data, ttl)`: Save data to localStorage with expiry
- `getFromCache(key)`: Retrieve cached data if not expired
- `clearCache(key)`: Remove specific cache entry
- `clearAllCache()`: Clear all app cache

## State Management (Pinia Stores)

### stores/auth.js

**State:**
- `user`: Object with user profile (email, displayName, userId)
- `isAuthenticated`: Boolean
- `isLoading`: Boolean for auth checks

**Getters:**
- `userName`: Returns displayName or email
- `userInitials`: Returns first letters for avatar

**Actions:**
- `checkAuth()`: Check if tokens exist and valid
- `login()`: Initiate Cognito OAuth flow
- `handleCallback(code)`: Process OAuth callback
- `logout()`: Clear auth state and redirect
- `refreshUser()`: Fetch latest user info

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
- `currentSession`: Object with session data
- `questions`: Array of questions for current session
- `currentQuestionIndex`: Integer
- `answers`: Array of user answers
- `sessionResults`: Object with score and detailed results
- `isSessionActive`: Boolean

**Getters:**
- `currentQuestion`: Returns current question object
- `progress`: Returns {current, total} for progress bar
- `score`: Returns {correct, total, percentage}

**Actions:**
- `startSession(vocabSetId, options)`: Initialize practice session
- `submitAnswer(answer)`: Submit answer for current question
- `nextQuestion()`: Move to next question
- `skipQuestion()`: Skip current question
- `endSession()`: Finalize and save session results
- `resetSession()`: Clear session state

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
- `login()`: Login function
- `logout()`: Logout function
- `checkAuth()`: Check authentication function

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

Handles image upload flow including S3 presigned URL and direct upload.

**Returns:**
- `uploadProgress`: Number 0-100
- `isUploading`: Boolean
- `error`: Error message
- `uploadImage(file)`: Async function that returns imageKey
- `reset()`: Reset upload state

**Implementation:**
- Request presigned URL from API
- Upload file directly to S3 with progress tracking
- Return S3 key for extraction trigger

### composables/usePractice.js

Practice session logic and answer validation.

**Returns:**
- `checkAnswer(userAnswer, correctAnswer)`: Boolean with fuzzy matching
- `calculateScore(answers)`: Return score object
- `formatFeedback(isCorrect, correctAnswer)`: Format feedback message

**Fuzzy Matching Rules:**
- Ignore case differences
- Ignore accents (café = cafe)
- Trim whitespace
- Accept answers within 1-2 character edit distance for words >5 chars
- Handle common typos (double letters, transpositions)

### composables/useToast.js

Toast notification wrapper for UI store.

**Returns:**
- `showSuccess(message)`: Show success toast
- `showError(message)`: Show error toast
- `showInfo(message)`: Show info toast
- `showWarning(message)`: Show warning toast

## Key Components

### components/upload/ImageDropzone.vue

Drag-and-drop file upload component with file validation.

**Features:**
- Drag-and-drop zone with hover states
- Click to browse file picker
- File type validation (JPG, PNG, HEIC)
- File size validation (max 10MB)
- Image preview before upload
- Progress bar during upload

**Props:**
- `accept`: String of accepted file types (default: 'image/jpeg,image/png,image/heic')
- `maxSize`: Number in bytes (default: 10485760 = 10MB)

**Events:**
- `@upload-success`: Emitted with imageKey when upload completes
- `@upload-error`: Emitted with error message

**Implementation Notes:**
- Use native drag-and-drop events (dragover, drop)
- Validate file type and size before upload
- Use FileReader for image preview
- Integrate with useUpload composable
- Show clear error messages for validation failures

### components/review/VocabTable.vue

Editable table for reviewing extracted vocabulary.

**Features:**
- Editable German and French columns
- Add/remove rows dynamically
- Reorder rows with drag handles
- Bulk select for deletion
- Validation indicators (empty fields highlighted)
- Metadata form (chapter, page, topic)

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
  german: 'das Haus',
  french: 'la maison',
  notes: '',
  order: 1
}
```

**Implementation Notes:**
- Use v-for with :key="item.itemId"
- Implement inline editing with input fields
- Add row: push new empty item to array
- Delete row: filter out by itemId
- Reorder: use drag-and-drop library (vue-draggable-next)
- Validate before emit: ensure no empty German/French pairs

### components/practice/QuestionCard.vue

Main practice interface showing question and answer input.

**Features:**
- Large, clear question text (German or French)
- Text input field for answer
- "Check" button (also triggered by Enter key)
- "Reveal Answer" option
- Visual feedback (green=correct, red=incorrect)
- Correct answer display when wrong

**Props:**
- `question`: Object with {itemId, german, french, direction}
- `direction`: String ('de-fr' or 'fr-de')

**Events:**
- `@submit`: Emitted with user answer
- `@reveal`: Emitted when user reveals answer
- `@next`: Emitted to move to next question

**State:**
- `userAnswer`: v-model for input
- `feedback`: Object with {isCorrect, message, correctAnswer}
- `isAnswered`: Boolean to show feedback

**Implementation Notes:**
- Focus input on mount
- Clear input on next question
- Handle Enter key for submit
- Show feedback for 2 seconds before enabling next
- Use fuzzy matching from usePractice composable
- Animate feedback appearance (transition)

### components/practice/SessionSummary.vue

End-of-session results display with statistics.

**Features:**
- Score display (X/Y correct, percentage)
- Time taken for session
- List of all questions with results
- Accuracy chart (Chart.js pie/donut)
- "Practice Again" button
- "Back to Dashboard" button

**Props:**
- `sessionResults`: Object with {score, duration, detailedResults, vocabSetId}

**Computed:**
- `percentage`: (correct / total) * 100
- `formattedDuration`: Convert seconds to "X min Y sec"
- `incorrectItems`: Filter detailedResults for wrong answers

**Implementation Notes:**
- Use Chart.js for visual score representation
- Show incorrect items prominently for review
- Offer to practice only missed words
- Save results to backend on mount

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

**Implementation Notes:**
- Use Tailwind card styling
- Lazy load image thumbnail
- Show progress as colored bar or circle
- Confirm before delete with modal

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
- Hero section with app description
- Key features overview (scan, review, practice)
- Screenshots/mockups
- "Get Started" button → login

**Implementation:**
- Check auth on mount → redirect to dashboard if authenticated
- Simple static content with Tailwind styling
- Responsive design for mobile/tablet/desktop

### views/DashboardView.vue

Main dashboard after login.

**Features:**
- Welcome message with user name
- Stats overview (total vocab sets, total words, practice streak)
- Grid of vocab set cards
- "Upload New" button (floating action button style)
- Recent practice sessions list

**Implementation:**
- Fetch vocab sets on mount
- Use VocabSetCard component in grid
- Responsive grid (1 col mobile, 2 col tablet, 3+ col desktop)
- Handle empty state (no vocab sets yet)

### views/UploadView.vue

Image upload and extraction flow.

**Features:**
- ImageDropzone component
- Upload progress display
- Extraction status polling
- Auto-redirect to review when complete

**Implementation:**
- Use useUpload composable
- After upload, trigger extraction API
- Poll extraction status every 2 seconds
- Show extraction progress (processing, extracting, structuring)
- Handle extraction errors gracefully
- Redirect to ReviewView with vocabSetId on success

### views/ReviewView.vue

Review and edit extracted vocabulary.

**Features:**
- Image preview (original uploaded image)
- VocabTable component
- Metadata form (chapter, page, topic)
- "Save" and "Cancel" buttons
- Validation before save

**Implementation:**
- Fetch vocab set by ID from route params
- Load extraction results if not yet approved
- Enable editing for pending vocab sets
- Show readonly view for approved sets
- Validate all items have German and French values
- Save to backend on approve
- Redirect to dashboard on save/cancel

### views/PracticeView.vue

Practice session interface.

**Features:**
- Direction selector (German→French or French→German)
- Number of questions selector
- QuestionCard component
- Progress bar at top
- Exit confirmation if session incomplete

**Implementation:**
- Get vocabSetId from route params
- Initialize session with practice store
- Show question by index from questions array
- Handle answer submission and feedback
- Move to next question after feedback shown
- Show SessionSummary when all questions complete
- Implement beforeRouteLeave guard for exit confirmation

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
- Full vocabulary list (read-only table)
- Edit button → ReviewView
- Practice button → PracticeView
- Delete button with confirmation
- Stats for this vocab set (times practiced, average score)

**Implementation:**
- Fetch vocab set by ID
- Show all items in scrollable table
- Action buttons at top
- Breadcrumb navigation (Dashboard > Vocab Set Name)

## Routing Configuration

### router/index.js

Vue Router setup with route guards.

**Routes:**
```javascript
[
  {
    path: '/',
    name: 'Landing',
    component: LandingView,
    meta: { requiresAuth: false }
  },
  {
    path: '/callback',
    name: 'Callback',
    component: CallbackView, // Handles OAuth callback
    meta: { requiresAuth: false }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: DashboardView,
    meta: { requiresAuth: true }
  },
  {
    path: '/upload',
    name: 'Upload',
    component: UploadView,
    meta: { requiresAuth: true }
  },
  {
    path: '/review/:vocabSetId',
    name: 'Review',
    component: ReviewView,
    meta: { requiresAuth: true },
    props: true
  },
  {
    path: '/practice/:vocabSetId',
    name: 'Practice',
    component: PracticeView,
    meta: { requiresAuth: true },
    props: true
  },
  {
    path: '/progress',
    name: 'Progress',
    component: ProgressView,
    meta: { requiresAuth: true }
  },
  {
    path: '/vocab/:vocabSetId',
    name: 'VocabSetDetail',
    component: VocabSetDetailView,
    meta: { requiresAuth: true },
    props: true
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: NotFoundView
  }
]
```

**Navigation Guards:**
- Global `beforeEach` guard: Check `meta.requiresAuth`
- If requires auth and not authenticated: redirect to landing/login
- If authenticated and on landing: redirect to dashboard
- Track route changes in analytics (optional)

## Styling Guidelines

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
- **Typography**: Base 16px, scale up for headings
- **Radius**: Consistent border-radius (rounded-lg for cards, rounded-md for inputs)
- **Shadows**: Subtle shadows (shadow-sm, shadow-md)
- **Transitions**: Use transition-all duration-200 for interactive elements

**Component Patterns:**
- **Buttons**: `bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-md transition-colors`
- **Cards**: `bg-white rounded-lg shadow-md p-6`
- **Inputs**: `border border-gray-300 rounded-md px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-transparent`

### Responsive Design

- **Breakpoints**: Use Tailwind defaults (sm: 640px, md: 768px, lg: 1024px, xl: 1280px)
- **Mobile-first**: Design for mobile, enhance for larger screens
- **Touch targets**: Minimum 44x44px for buttons on mobile
- **Font scaling**: Slightly larger base font on mobile (text-base → text-lg)

## Form Validation

### Validation Rules

**Upload:**
- File type: Must be image/jpeg, image/png, or image/heic
- File size: Maximum 10MB
- Required: At least one file selected

**Review:**
- German field: Required, 1-100 characters
- French field: Required, 1-100 characters
- Chapter: Optional, max 50 characters
- Page: Optional, must be positive integer
- Topic: Optional, max 100 characters

**Practice:**
- Answer: Required (cannot submit empty)

### Validation Implementation

Use VeeValidate or custom validation utilities:

**utils/validators.js:**
```javascript
export const required = (value) => !!value || 'This field is required'
export const maxLength = (max) => (value) => 
  !value || value.length <= max || `Maximum ${max} characters`
export const minLength = (min) => (value) => 
  !value || value.length >= min || `Minimum ${min} characters`
export const isPositiveInteger = (value) => 
  !value || (Number.isInteger(Number(value)) && Number(value) > 0) || 'Must be a positive number'
```

Display validation errors inline below fields with red text.

## Error Handling

### Error Types and Responses

**Network Errors:**
- Show toast: "Connection problem. Please check your internet."
- Retry button for failed requests

**Authentication Errors (401):**
- Clear tokens
- Redirect to landing page with message: "Session expired. Please log in again."

**Authorization Errors (403):**
- Show toast: "You don't have permission to perform this action."
- Redirect to dashboard

**Validation Errors (400):**
- Display field-specific errors from API response
- Highlight invalid fields

**Server Errors (500):**
- Show toast: "Something went wrong. Please try again."
- Log error details to console
- Optionally send to error tracking service

**Not Found (404):**
- Show "Resource not found" message
- Provide link back to dashboard

### Error Boundaries

Implement global error handler in App.vue to catch uncaught errors:
```javascript
app.config.errorHandler = (err, instance, info) => {
  console.error('Global error:', err, info)
  // Show generic error toast
  // Send to monitoring service
}
```

## Performance Optimization

### Code Splitting

- Lazy load routes: `component: () => import('./views/DashboardView.vue')`
- Lazy load heavy components (Chart.js) only when needed
- Dynamic imports for large libraries

### Image Optimization

- Use lazy loading for vocab set thumbnails: `loading="lazy"`
- Serve responsive images from S3 with CloudFront
- Consider WebP format with fallback to JPEG

### API Optimization

- Implement request caching in storage.js (short TTL for list endpoints)
- Debounce search/filter inputs (300ms delay)
- Paginate vocab set lists if count grows large

### Bundle Size

- Tree-shake unused Tailwind classes with purge configuration
- Minimize dependencies (check bundle analyzer)
- Use CDN for large libraries if beneficial

## Testing Strategy

### Unit Tests (Vitest)

**Priority Components:**
- Validators (utils/validators.js)
- Fuzzy matching logic (utils/fuzzyMatch.js)
- Composables (useApi, usePractice)
- Pinia stores (actions and getters)

**Example Test Pattern:**
```javascript
describe('fuzzyMatch', () => {
  it('should match exact strings', () => {
    expect(fuzzyMatch('café', 'café')).toBe(true)
  })
  
  it('should match ignoring accents', () => {
    expect(fuzzyMatch('cafe', 'café')).toBe(true)
  })
  
  it('should allow minor typos', () => {
    expect(fuzzyMatch('maison', 'maisom')).toBe(true)
  })
})
```

### Component Tests (Vue Test Utils)

**Priority Components:**
- QuestionCard.vue (answer submission, feedback display)
- VocabTable.vue (editing, adding/removing rows)
- ImageDropzone.vue (file validation, upload trigger)

**Test Pattern:**
```javascript
describe('QuestionCard', () => {
  it('should emit submit event with answer', async () => {
    const wrapper = mount(QuestionCard, {
      props: { question: mockQuestion }
    })
    
    await wrapper.find('input').setValue('la maison')
    await wrapper.find('button').trigger('click')
    
    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')[0][0]).toBe('la maison')
  })
})
```

### E2E Tests (Playwright)

**Critical User Flows:**
1. Authentication: Login → Dashboard → Logout
2. Upload: Login → Upload image → Review → Save → Dashboard
3. Practice: Login → Select vocab set → Complete session → View results

**Test Environment:**
- Use staging environment with test Cognito user pool
- Mock S3 uploads and Textract responses
- Reset test database between runs

## Accessibility (a11y)

### Requirements

- **Keyboard Navigation**: All interactive elements accessible via keyboard (Tab, Enter, Esc)
- **Screen Reader Support**: Proper ARIA labels, landmarks, and announcements
- **Color Contrast**: WCAG AA compliance (4.5:1 for normal text)
- **Focus Indicators**: Clear focus outlines on all interactive elements
- **Alt Text**: All images have descriptive alt attributes

### Implementation Checklist

- Use semantic HTML (button, nav, main, article)
- Add `role` attributes where semantic HTML insufficient
- Use `aria-label` for icon buttons
- Announce dynamic content changes with `aria-live` regions
- Implement skip links ("Skip to main content")
- Test with keyboard only (no mouse)
- Test with screen reader (VoiceOver on Mac, NVDA on Windows)

**Example Patterns:**
```vue
<!-- Icon button with label -->
<button aria-label="Delete vocabulary set" @click="deleteVocabSet">
  <TrashIcon />
</button>

<!-- Live region for dynamic feedback -->
<div aria-live="polite" aria-atomic="true">
  {{ feedbackMessage }}
</div>

<!-- Modal with focus trap -->
<dialog role="dialog" aria-labelledby="modal-title" aria-modal="true">
  <h2 id="modal-title">Confirm Deletion</h2>
  <!-- ... -->
</dialog>
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
- Bucket policy: Public read access for website content

**Upload Process:**
```bash
aws s3 sync dist/ s3://vocab-trainer-frontend --delete
```

**CloudFront Configuration:**
- Origin: S3 bucket website endpoint
- Default root object: `index.html`
- Custom error responses: 404 → /index.html