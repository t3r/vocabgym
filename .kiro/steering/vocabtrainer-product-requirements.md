# VocabTrainer Product Requirements

## Executive Summary

VocabTrainer is a web-based vocabulary training application designed for German Gymnasium students learning foreign languages. The application supports multiple target languages (French, English, Spanish, Italian) with German as the source language. Its core innovation is automated vocabulary extraction from scanned workbook images using a two-stage AI pipeline (Textract OCR + Amazon Bedrock), eliminating manual data entry while ensuring students practice with their actual curriculum materials.

The application features two user roles: **students** and **teachers**. Teachers can create Ligen (leagues) to organize students, assign vocabulary sets, and track progress across their class. AI-assisted learning with smart repetition and error pattern analysis helps students focus on their weak areas.

### Key Differentiators
- **Curriculum-aligned**: Uses actual workbook content rather than generic vocabulary lists
- **Automated extraction**: Two-stage AI pipeline (Textract + Bedrock) converts workbook pages into practice material, handling both tables and free-text layouts
- **Immediate practice**: Scan → Review → Practice workflow in minutes
- **AI-assisted learning**: Smart repetition prioritizes weak words; error pattern analysis provides personalized learning hints (Lernhinweise)
- **Multi-language support**: German → French, English, Spanish, or Italian
- **Liga system**: Teachers create leagues for classroom management with leaderboards and streak tracking
- **Progress tracking**: Monitors mastery levels, practice history, and error patterns

### Target Audience
- Primary: Gymnasium students learning foreign languages (French, English, Spanish, Italian)
- Secondary: Teachers managing classroom vocabulary practice via Ligen
- Tertiary: Parents monitoring student progress
- Context: Students have workbooks with vocabulary content (tables or lists)

## Problem Statement

Students learning foreign languages in German Gymnasiums face several challenges:

1. **Manual entry burden**: Typing vocabulary lists from workbooks is time-consuming and error-prone
2. **Generic apps don't match curriculum**: Apps like Anki or Quizlet require manual setup and don't align with specific textbook content
3. **Motivation gap**: Students are more engaged when practicing their own materials
4. **Fragmented workflow**: Separate tools for vocabulary management and practice
5. **No classroom integration**: Teachers lack tools to assign vocabulary and track class progress
6. **One-size-fits-all practice**: Traditional apps don't adapt to individual error patterns

### Solution
A unified web application that scans workbook pages, extracts vocabulary automatically via AI, and provides immediate typing-based practice sessions with AI-assisted learning, progress tracking, and classroom management through the Liga system.

## User Personas

### Primary Persona: Sophie (Student)
- **Age**: 14 years old
- **Context**: Attends Gymnasium, learning French as second foreign language
- **Tech comfort**: High - uses iPad daily for schoolwork
- **Goals**: 
  - Prepare for upcoming vocabulary tests
  - Maintain daily practice routine
  - Avoid tedious manual list creation
  - Climb the Liga leaderboard
- **Pain points**:
  - Limited study time due to multiple subjects
  - Loses motivation with generic vocabulary apps
  - Handwriting practice lists takes too long
  - Keeps making the same mistakes (e.g., wrong articles)

### Secondary Persona: Herr Müller (Teacher)
- **Age**: 38 years old
- **Context**: French teacher at a Gymnasium, manages multiple classes
- **Tech comfort**: Moderate - uses school tools and basic web apps
- **Goals**:
  - Assign vocabulary practice aligned with curriculum
  - Monitor which students are practicing regularly
  - Identify students who are struggling
  - Motivate students through friendly competition
- **Pain points**:
  - No visibility into student study habits
  - Cannot easily distribute vocabulary lists digitally
  - Difficult to track who is preparing for tests

### Tertiary Persona: Parent/Guardian
- **Goals**: 
  - Monitor child's study consistency
  - Ensure practice aligns with school curriculum
  - Support learning without constant supervision
- **Needs**:
  - Progress visibility
  - Simple setup process
  - Reliable, safe platform

## User Roles & Permissions

### Student Role (Default)
- Create and manage own vocabulary sets
- Upload workbook images and review extractions
- Practice vocabulary with AI-assisted learning
- Join one Liga (league) via 6-character join code
- View Liga leaderboard and own statistics
- Set and update display name
- UI uses Du-Form (informal German, appropriate for teenagers)

### Teacher Role
- All student capabilities
- Create and manage Ligen (leagues) with auto-generated 6-character join codes
- Assign vocabulary sets to Liga members
- View member statistics and progress
- Remove members from Liga
- Configure Liga leaderboard score mode
- UI uses Sie-Form (formal German, appropriate for adults)
- Role assigned via Cognito 'teachers' group membership

### Display Name Policy
- All users set a display name via the application header
- Display names are shown on leaderboards and in Liga member lists
- Email addresses are **never** shown to other users
- Display names are required for Liga participation

## Core Features & Requirements

### 1. User Authentication & Management

**Requirements:**
- Multi-user support with individual accounts
- Secure authentication using AWS Cognito
- OAuth2 flow with Cognito-hosted login UI
- Two user roles: student (default) and teacher (via Cognito 'teachers' group)
- User profile with display name and basic statistics
- Display name settable/editable via application header
- Password reset functionality
- Email verification on signup
- Email addresses never exposed to other users

**User Stories:**
- As a student, I want to create an account with my email so I can save my vocabulary lists
- As a student, I want to log in securely so my data remains private
- As a student, I want to set a display name so my classmates see my name on the leaderboard
- As a student, I want to reset my password if I forget it
- As a teacher, I want to log in and have access to teacher features automatically
- As a parent, I want to help my child set up their account safely

**Acceptance Criteria:**
- User can register with email and password
- Email verification required before first login
- Session persists across browser refreshes
- Logout clears all authentication tokens
- Failed login attempts are rate-limited
- Display name can be set and changed via the header UI
- Teacher role is determined by Cognito 'teachers' group membership
- Student UI uses Du-Form; teacher UI uses Sie-Form

### 2. Image Upload & Processing

**Requirements:**
- Support image formats: JPG, PNG (HEIC rejected at file input level; iOS auto-converts to JPEG)
- Maximum file size: 10MB per image
- **Multi-image upload**: Multiple pages can be uploaded per vocabulary set
- Drag-and-drop interface for easy upload
- Alternative file picker for traditional upload
- Image preview before processing
- Processing status indicator with estimated time
- S3 storage with automatic lifecycle management (delete after 30 days)
- Each vocabulary item linked to its source image

**User Stories:**
- As a student, I want to drag and drop my workbook photos into the app
- As a student, I want to upload multiple pages for the same vocabulary set
- As a student, I want to see a preview of my uploaded images to confirm they're correct
- As a student, I want to know when processing is complete
- As a student, I want clear error messages if my image is rejected

**Acceptance Criteria:**
- Upload accepts JPG, PNG formats; HEIC is rejected at the file input level
- iOS devices auto-convert HEIC to JPEG before upload
- Multiple images can be uploaded for a single vocabulary set
- File size validation occurs client-side before upload
- Upload progress bar shows percentage complete
- Processing status updates in real-time
- Clear error messages for unsupported formats or oversized files
- Images are compressed if over 5MB before storage
- Extracted vocabulary items maintain a reference to their source image

**Technical Notes:**
- Use S3 presigned URLs for direct browser-to-S3 upload
- Client-side image compression to optimize upload speed
- Store original image references with vocabulary set metadata
- Each vocab item stores the source image key it was extracted from

### 3. Vocabulary Extraction & Review

**Requirements:**
- Two-stage AI extraction pipeline:
  - **Stage 1**: AWS Textract for raw OCR text extraction from workbook images
  - **Stage 2**: Amazon Bedrock (Amazon Nova Pro, `eu.amazon.nova-pro-v1:0`) extracts structured vocabulary pairs from raw OCR text
- Handles both table layouts and free-text/list layouts
- Extract German ↔ target language vocabulary pairs (target language determined by VocabSet)
- Manual review interface before finalizing vocabulary set
- Editable table view with add/remove/modify capabilities
- Metadata fields: chapter number, page number, topic/title, target language, date created
- Bulk operations: approve all, delete all, reprocess image

**User Stories:**
- As a student, I want the app to automatically find vocabulary in my workbook photo
- As a student, I want extraction to work with tables, lists, and free-text layouts
- As a student, I want to review extracted vocabulary before it's saved
- As a student, I want to fix any extraction mistakes easily
- As a student, I want to add vocabulary pairs that were missed
- As a student, I want to delete extracted words that aren't vocabulary (page headers, etc.)
- As a student, I want to organize vocabulary by chapter and topic
- As a student, I want to specify which language I'm learning for this vocabulary set

**Acceptance Criteria:**
- Extraction completes within 30 seconds for typical workbook page
- Review interface displays extracted pairs in editable table
- Each row can be edited inline (German and target language columns)
- Add row button inserts new blank row
- Delete row button removes individual entries
- Target language selection per vocabulary set (FR, EN, ES, IT)
- Chapter/page/topic fields are optional but recommended
- "Approve" button saves vocabulary set and enables practice
- "Reprocess" button triggers new extraction attempt
- Extraction handles free-text layouts, not just tables

**Edge Cases:**
- Multiple tables on one page: Extract all vocabulary pairs
- Mixed content (exercises + vocabulary): AI filters to vocabulary content
- Free-text vocabulary lists: Bedrock extracts pairs from unstructured text
- Tilted/skewed images: Textract handles orientation
- Poor image quality: Display warning suggesting retake if extraction yields poor results
- Multi-page sets: Items from each page linked to source image

**Technical Notes:**
- Stage 1: Textract extracts raw text from the image
- Stage 2: Bedrock (Amazon Nova Pro, `eu.amazon.nova-pro-v1:0`) processes raw OCR text to identify and structure vocabulary pairs
- No OpenAI dependency — Bedrock handles all AI extraction
- Each VocabSet has a `targetLanguage` field (FR, EN, ES, IT)
- Source language is always German

### 4. Vocabulary Organization & Management

**Requirements:**
- Dashboard view listing all vocabulary sets
- Each set displays: title, target language, item count, creation date, last practiced date, mastery percentage
- Sort options: by date, by title, by mastery level, by target language
- Filter options: by chapter, by date range, by mastery status, by target language
- Search across all vocabulary sets
- Archive functionality (hide without deleting)
- Bulk delete for multiple sets
- Export vocabulary set as CSV or printable PDF

**User Stories:**
- As a student, I want to see all my vocabulary sets organized on one page
- As a student, I want to quickly find vocabulary from a specific chapter
- As a student, I want to filter by language to see only my French sets
- As a student, I want to archive old vocabulary I no longer need to practice
- As a student, I want to export vocabulary to share with classmates or print

**Acceptance Criteria:**
- Dashboard loads all sets within 2 seconds
- Vocabulary sets display as cards with key metadata including target language
- Clicking a set opens detail view
- Search updates results in real-time
- Archive moves set to separate "Archived" tab
- Delete requires confirmation dialog
- Export generates formatted CSV with German, target language, and Notes columns

### 5. Practice Session Interface

**Requirements:**
- User selects vocabulary set to practice from dashboard
- Practice mode selection: German → target language or target language → German
- **AI-assisted smart repetition**: Weighted question selection based on mastery level and error history — weak words appear more frequently
- Large, clear text input field for answer entry
- "Check Answer" button (keyboard shortcut: Enter)
- Immediate feedback: correct (green) or incorrect (red)
- Display correct answer after incorrect attempt
- "Next Question" button to continue
- Progress bar showing position in session
- Option to skip question (marks as incorrect)
- Session summary at completion: score, time taken, detailed results
- **Error pattern analysis (Lernhinweis)**: After each session, display personalized learning hints based on detected error patterns

**User Stories:**
- As a student, I want to practice typing target language words when shown German
- As a student, I want to also practice typing German when shown the target language
- As a student, I want immediate feedback so I know if I'm correct
- As a student, I want to see the correct answer when I'm wrong so I can learn
- As a student, I want weak words to appear more often so I focus on what I need to learn
- As a student, I want to see learning hints (Lernhinweise) after practice showing my common mistakes
- As a student, I want to see my score as I practice to track improvement
- As a student, I want a summary at the end showing what I got right and wrong

**Acceptance Criteria:**
- Practice session uses weighted question selection (smart repetition)
- Words with lower mastery and more errors are prioritized
- Questions appear in weighted-random order, not purely random
- User cannot proceed without answering or skipping
- Answer checking is case-insensitive
- Fuzzy matching accepts minor typos (Levenshtein distance ≤ 2 for words >5 chars)
- Accepts common variations (café = cafe, naïve = naive)
- Correct answers show green checkmark
- Incorrect answers show red X and display correct answer
- Progress bar updates after each question
- Session summary displays: total score (X/Y), percentage, time elapsed
- Summary includes list of all questions with user's answer vs. correct answer
- Session summary includes Lernhinweis section with error pattern analysis

**Answer Validation Logic:**
- Normalize answers: trim whitespace, lowercase
- Accept articles with or without (der/die/das for German; le/la/les for French; el/la for Spanish; il/la for Italian; the/a for English)
- Accept accented and non-accented characters as equivalent
- For compound answers (multiple correct options), accept any valid option
- Mark answer correct if fuzzy match score > 85%

**Technical Notes:**
- Use Levenshtein distance algorithm for fuzzy matching
- Frontend handles answer validation for instant feedback
- Backend records detailed results for progress tracking
- Session state stored in browser local storage to survive page refresh
- Smart repetition algorithm weights questions by: mastery level (lower = higher weight), error count (more errors = higher weight), time since last practice (longer = higher weight)

### 6. AI-Assisted Learning

**Requirements:**
- **Smart repetition**: Weighted question selection during practice sessions based on mastery level, error count, and recency
- **Error pattern tracking**: Store the last 5 wrong answers per vocabulary item
- **Error pattern detection**: Detect common error types including article errors (e.g., confusing le/la) and repeated mistakes
- **Lernhinweis (learning hints)**: After each practice session, display personalized analysis of error patterns

**User Stories:**
- As a student, I want the app to automatically focus on words I struggle with
- As a student, I want to understand why I keep getting certain words wrong
- As a student, I want to see if I'm confusing articles or making the same typos repeatedly
- As a student, I want personalized tips after each session to improve

**Acceptance Criteria:**
- During practice, words with lower mastery appear earlier and more frequently
- The system stores the last 5 incorrect answers for each vocabulary item
- After a practice session, the system analyzes wrong answers to detect patterns
- Article errors are specifically detected and highlighted (e.g., "Du verwechselst oft le/la")
- Repeated identical mistakes are flagged
- Lernhinweis section appears in session summary with actionable feedback
- Error pattern data persists across sessions for long-term analysis

**Algorithm:**
- Question weight = `(5 - masteryLevel) * 2 + errorCount + daysSinceLastPractice * 0.5`
- Higher weight = higher probability of being selected
- Error patterns detected by comparing last 5 wrong answers against correct answer
- Article errors: check if wrong answer differs only in article
- Repeated mistakes: check if same wrong answer appears ≥ 3 times in last 5 attempts

### 7. Liga (League) System

**Requirements:**
- Teachers can create Ligen (leagues) for classroom management
- Each Liga has an auto-generated 6-character alphanumeric join code
- Students join a Liga by entering the join code
- Each student can be a member of at most one Liga
- Liga features:
  - Leaderboard with configurable score modes
  - Streak tracking per member
  - Teacher can assign vocabulary sets to Liga members
  - Teacher can view member statistics and progress
  - Teacher can remove members from the Liga

**Score Modes (configurable by teacher):**
- **Total**: Cumulative points from all practice sessions
- **Weekly**: Points earned in the current week only
- **Accuracy**: Ranked by overall accuracy percentage
- **Combined**: Weighted combination of practice volume and accuracy

**User Stories:**
- As a teacher, I want to create a Liga for my class with a shareable join code
- As a teacher, I want to assign vocabulary sets so all students practice the same material
- As a teacher, I want to see which students are practicing and their scores
- As a teacher, I want to remove students who are no longer in my class
- As a teacher, I want to choose how the leaderboard ranks students
- As a student, I want to join my teacher's Liga using a code
- As a student, I want to see the leaderboard to compare my progress with classmates
- As a student, I want to maintain a practice streak to climb the leaderboard

**Acceptance Criteria:**
- Only teachers can create Ligen
- Join code is 6 characters, alphanumeric, unique
- Students enter join code to become Liga members
- A student can only be in one Liga at a time (must leave before joining another)
- Leaderboard displays member display names (never email addresses)
- Leaderboard updates after each completed practice session
- Teacher can switch between score modes at any time
- Teacher can assign vocabulary sets that appear in all members' dashboards
- Teacher can view per-member statistics (sessions, accuracy, streak)
- Teacher can remove members from the Liga
- Streak tracking: consecutive days with at least one completed practice session

**Technical Notes:**
- Liga data stored in DynamoDB with join code as lookup key
- Membership stored as separate records for efficient queries
- Leaderboard calculated on-demand or cached with short TTL
- Assigned vocabulary sets stored as references in Liga metadata

### 8. Progress Tracking & Analytics

**Requirements:**
- Per-vocabulary-set statistics: mastery level, accuracy percentage, practice count
- Per-item tracking: correct attempts, incorrect attempts, last practiced date, last 5 wrong answers
- Mastery levels: 0 (never practiced) → 5 (consistently correct)
- Overall dashboard: total words learned, average accuracy, practice streak
- Visual progress indicators: bar charts, line graphs, heatmaps
- Practice history: calendar view showing practice days
- Detailed session history: list of past sessions with scores
- Liga context: teachers can view aggregated class statistics

**User Stories:**
- As a student, I want to see which words I've mastered
- As a student, I want to see which words I consistently get wrong and my error patterns
- As a student, I want to track my practice streak to stay motivated
- As a student, I want visual graphs showing my improvement over time
- As a teacher, I want to see class-wide progress in my Liga
- As a parent, I want to see if my child is practicing regularly

**Acceptance Criteria:**
- Dashboard shows total vocabulary count and overall mastery percentage
- Each vocabulary set displays mastery level (0-100%)
- Item detail view shows per-word statistics including error history
- Practice history calendar highlights days with completed sessions
- Graphs update after each practice session
- Mastery level increases after 3 consecutive correct answers
- Mastery level decreases after 2 consecutive incorrect answers
- Streak count displayed prominently for motivation

**Mastery Level Algorithm:**
```
Level 0: Never practiced
Level 1: Practiced 1-2 times (any result)
Level 2: 50%+ accuracy over last 3 attempts
Level 3: 75%+ accuracy over last 5 attempts
Level 4: 90%+ accuracy over last 5 attempts
Level 5: 100% accuracy over last 5 attempts
```

**Visual Components:**
- Accuracy trend line graph (x-axis: date, y-axis: percentage)
- Mastery distribution pie chart (how many words at each level)
- Practice frequency heatmap (GitHub-style calendar)
- Top struggled words list (words with lowest accuracy)
- Top mastered words list (words with highest accuracy)
- Liga leaderboard (for Liga members)

**Technical Notes:**
- Calculate statistics on-demand from practice session data
- Cache aggregate statistics in DynamoDB for performance
- Update cached stats after each completed session
- Use Chart.js or similar library for visualizations
- Error pattern data (last 5 wrong answers per item) stored in Progress table

### 9. User Interface & Experience

**Design Principles:**
- Clean, minimal, distraction-free
- **All UI text in German** (Deutsche Benutzeroberfläche)
- **Du-Form** for students, **Sie-Form** for teachers
- **Full dark mode support** throughout the application
- Mobile-responsive (works on iPad, laptop, desktop)
- Fast load times (< 2 seconds per page)
- Keyboard shortcuts for power users
- Clear visual hierarchy
- Accessible (WCAG 2.1 AA compliant)

**Color Scheme:**
- Primary: Blue (#3B82F6) - trust, learning
- Success: Green (#10B981) - correct answers
- Error: Red (#EF4444) - incorrect answers
- Neutral: Gray scale for text and backgrounds
- Accent: Purple (#8B5CF6) - highlights, CTAs
- Dark mode: Full dark color palette with appropriate contrast ratios

**Typography:**
- Headers: Inter or similar sans-serif (bold)
- Body: Inter regular
- Vocabulary display: Larger size (18-20px) for readability
- High contrast ratios for accessibility (in both light and dark mode)

**Layout:**
- Dashboard: Card-based grid layout
- Practice: Centered, single-column focus mode
- Review: Spreadsheet-style table view
- Liga: Leaderboard view with member cards
- Navigation: Top bar with logo, display name, user menu, main navigation links

**Responsive Breakpoints:**
- Mobile: < 640px (single column)
- Tablet: 640px - 1024px (2 columns)
- Desktop: > 1024px (3 columns on dashboard)

**Dark Mode:**
- Toggle accessible from the application UI
- Persisted as user preference
- All components, views, and charts support dark mode
- Respects system preference as default

**Loading States:**
- Skeleton loaders for content
- Spinner for processing operations
- Progress bars for uploads and extractions

**Error Handling:**
- Toast notifications for transient errors (German messages)
- Inline validation messages for forms
- Error pages for critical failures (500, 404)
- Retry buttons where applicable

## Technical Requirements

### Performance
- Page load time < 2 seconds on 3G connection
- API response time < 500ms for standard operations
- Image upload < 10 seconds for 5MB file
- Vocabulary extraction < 30 seconds per page
- Practice session startup < 1 second

### Security
- All API endpoints require authentication
- Teacher role enforced via Cognito 'teachers' group
- Images stored in private S3 bucket with presigned URLs
- User data encrypted at rest (DynamoDB encryption)
- TLS 1.3 for all data in transit
- CORS properly configured for frontend domain only
- Input validation on all user-submitted data
- Rate limiting on API endpoints (100 requests/minute per user)
- XSS protection (sanitize user input)
- Email addresses never exposed to other users in any API response

### Scalability
- Support up to 1000 concurrent users
- Handle 10,000 vocabulary sets total
- Process 100 images per hour
- Store up to 100,000 practice session records
- DynamoDB auto-scaling enabled
- Lambda concurrency limits configured

### Availability
- 99.5% uptime target
- Graceful degradation if OCR/AI service unavailable
- Automatic retries for failed API calls
- Health check endpoints for monitoring
- CloudWatch alarms for critical failures

### Browser Support
- Chrome/Edge: Latest 2 versions
- Safari: Latest 2 versions
- Firefox: Latest 2 versions
- Mobile Safari (iOS): Latest 2 versions
- Chrome Mobile (Android): Latest 2 versions

### Accessibility
- WCAG 2.1 AA compliance
- Keyboard navigation for all interactions
- Screen reader compatible
- Sufficient color contrast ratios (both light and dark mode)
- Focus indicators on interactive elements
- Alt text for all images
- ARIA labels where appropriate

## Data Privacy & Compliance

### Data Collection
- Email address (required for account, never shown to other users)
- Display name (set by user, shown on leaderboards)
- Uploaded workbook images (stored 30 days)
- Extracted vocabulary data
- Practice session results and error patterns
- Liga membership data
- Usage analytics (anonymized)

### Data Retention
- User accounts: Retained until user deletion request
- Vocabulary sets: Retained until user deletion
- Uploaded images: Auto-deleted after 30 days
- Practice sessions: Retained indefinitely (for progress tracking)
- Error patterns: Retained with practice data
- Liga data: Retained until Liga is deleted by teacher
- Deleted accounts: 30-day grace period before permanent deletion

### User Rights
- Right to access: Export all user data as JSON
- Right to deletion: Delete account and all associated data
- Right to correction: Edit any stored vocabulary or profile data
- Transparent data usage: Clear privacy policy

### GDPR Considerations
- Obtain consent before data collection
- Provide clear privacy policy
- Enable data export functionality
- Enable account deletion functionality
- Process data only for stated purposes
- No third-party data sharing without consent
- Email addresses protected from exposure to other users

## Success Metrics

### User Engagement
- Daily active users (DAU)
- Weekly active users (WAU)
- Average session duration
- Practice sessions per week per user
- Vocabulary sets created per user
- User retention rate (7-day, 30-day)
- Liga participation rate
- Average streak length

### Feature Adoption
- Percentage of users who upload at least one image
- Percentage of extractions that are approved without edits
- Average edit count per vocabulary review
- Most used practice direction (German→target language vs. reverse)
- Most used target language (FR, EN, ES, IT)
- Liga creation rate (teachers)
- Liga join rate (students)
- Lernhinweis engagement (do students review their error patterns?)

### Learning Outcomes
- Average mastery level progression over time
- Average accuracy improvement over 30 days
- Vocabulary retention rate (tested via re-practice after 7 days)
- Practice streak length distribution
- Error pattern reduction over time (do detected patterns decrease?)
- Impact of smart repetition on mastery progression

### Technical Performance
- API response time (p50, p95, p99)
- Image upload success rate
- Extraction accuracy rate (measured by user edit frequency)
- Bedrock extraction quality (compared to Textract-only)
- Error rate by endpoint
- Frontend page load times

## Future Enhancements (Out of Scope for Current Release)

### Potential Features
- Audio pronunciation for vocabulary words (text-to-speech)
- Multiple choice practice mode
- Spaced repetition with scheduled review reminders
- Mobile native apps (iOS, Android)
- Handwriting input for iPad (using Apple Pencil)
- Study reminders via email or push notifications
- Integration with popular textbook publishers
- Gamification: badges and achievements beyond streaks
- Support for additional language pairs (e.g., Latin)
- Offline mode with sync
- Vocabulary generation from any text (not just workbook pages)

## Constraints & Assumptions

### Assumptions
- Students have access to iPad, laptop, or desktop browser
- Workbook pages contain vocabulary in table or list format
- Students are motivated to use digital tools for studying
- Internet connection available during study sessions
- Vocabulary workbooks use standard Roman alphabet (no Cyrillic, Arabic, etc.)
- Teachers have access to create Cognito accounts with teacher group membership

### Constraints
- Budget: Optimize for low AWS costs (target <$50/month for 100 users)
- Technical: Must use AWS services for all infrastructure (Bedrock for AI, not OpenAI)
- Language: Source language is always German; target languages limited to FR, EN, ES, IT
- Liga: One Liga per student to keep the system simple

### Known Limitations
- OCR accuracy depends on image quality (requires good lighting, focus)
- Handwritten annotations may not extract reliably
- No offline mode (requires internet connection)
- HEIC images must be converted to JPEG before upload (iOS does this automatically)
- No real-time collaboration features within practice sessions

## Glossary

- **Vocabulary Set (VocabSet)**: A collection of German ↔ target language word pairs extracted from workbook pages or manually created, with a specified target language
- **Target Language**: The foreign language being learned (FR, EN, ES, IT); German is always the source language
- **Practice Session**: A quiz where users type answers to vocabulary questions with AI-assisted question selection
- **Mastery Level**: A 0-5 scale indicating how well a user knows a vocabulary item
- **Extraction**: The two-stage AI pipeline (Textract OCR + Bedrock) that converts workbook images into structured vocabulary data
- **Review Interface**: The editable table view where users verify and correct extracted vocabulary
- **Fuzzy Matching**: Approximate string matching that accepts minor typos as correct
- **Lernhinweis**: Learning hint — personalized feedback shown after practice sessions based on error pattern analysis
- **Liga**: A league/group created by a teacher for classroom management, with leaderboard and streak tracking
- **Join Code**: A 6-character alphanumeric code used by students to join a Liga
- **Smart Repetition**: AI-driven question selection that prioritizes weak words based on mastery level, error count, and recency
- **Error Pattern**: Detected recurring mistake types (e.g., article confusion, repeated typos) tracked per vocabulary item
- **Du-Form**: Informal German address used in the student UI
- **Sie-Form**: Formal German address used in the teacher UI
- **Gymnasium**: German secondary school (grades 5-12/13) preparing students for university
- **Dark Mode**: Full dark color theme supported throughout the application

## Appendix: User Flow Diagrams

### Primary Flow: Scan to Practice
1. User uploads one or more workbook images via drag-and-drop
2. User selects target language for the vocabulary set (FR, EN, ES, IT)
3. System displays upload progress for each image
4. System triggers two-stage extraction (Textract OCR → Bedrock vocabulary extraction)
5. System parses extraction results into German ↔ target language pairs
6. User reviews extracted vocabulary in editable table (items linked to source images)
7. User corrects any extraction errors
8. User adds metadata (chapter, topic)
9. User clicks "Approve" to save vocabulary set
10. User clicks "Start Practice" from dashboard
11. User selects practice direction (German → target language or reverse)
12. System uses smart repetition to select and order questions (weak words first)
13. User types answer and presses Enter
14. System validates answer and shows feedback
15. User proceeds to next question
16. System displays session summary at completion with Lernhinweis (error pattern analysis)
17. System updates progress statistics and error pattern data

### Liga Flow: Teacher Creates and Manages Liga
1. Teacher creates a new Liga, receives 6-character join code
2. Teacher shares join code with students (verbally, on board, etc.)
3. Students enter join code to join the Liga
4. Teacher assigns vocabulary sets to the Liga
5. Students see assigned sets in their dashboard
6. Students practice and their scores appear on the leaderboard
7. Teacher views member statistics, identifies struggling students
8. Teacher configures leaderboard score mode as needed

### Secondary Flow: Browse and Manage
1. User views dashboard with all vocabulary sets (filtered by target language if desired)
2. User searches or filters for specific set
3. User clicks on vocabulary set card
4. User views detailed statistics for that set including error patterns
5. User optionally edits vocabulary items
6. User archives or deletes set if needed

### Error Flow: Failed Extraction
1. User uploads image
2. System attempts two-stage extraction (Textract → Bedrock)
3. Extraction fails or returns poor quality results
4. System displays error message with retry option
5. User retakes photo with better lighting/angle
6. User retries upload
7. If extraction still fails, user enters vocabulary manually

## Resolved Questions

1. ~~Should the app support collaborative features?~~ → **Yes, via Liga system. Teachers create leagues, students join and compete on leaderboards.**
2. ~~Should there be a mobile app in addition to web?~~ → **Web-only for now, mobile-responsive.**
3. ~~Support for additional language pairs?~~ → **Implemented: FR, EN, ES, IT as target languages with German as source.**
4. ~~Teacher dashboard for classroom management?~~ → **Implemented via Liga system.**
5. ~~Spaced repetition algorithm?~~ → **Implemented as smart repetition with weighted question selection.**
6. ~~Gamification?~~ → **Partially implemented: Liga leaderboards and streak tracking.**

## Open Questions

1. Should there be a time limit per practice question, or allow unlimited time?
2. How should compound words be handled (German: "der Tisch" vs "Tisch")?
3. What level of parental controls or monitoring is needed?
4. Should practice sessions be resumable if interrupted?
5. How to handle vocabulary with multiple correct translations?
6. Should teachers be able to create multiple Ligen (e.g., one per class)?
7. Should there be inter-Liga competitions or school-wide leaderboards?
