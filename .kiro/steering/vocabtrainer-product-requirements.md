# VocabTrainer Product Requirements

## Executive Summary

VocabTrainer is a web-based vocabulary training application designed for 9th grade German Gymnasium students learning French. The application's core innovation is automated vocabulary extraction from scanned workbook images, eliminating manual data entry while ensuring students practice with their actual curriculum materials.

### Key Differentiators
- **Curriculum-aligned**: Uses actual workbook content rather than generic vocabulary lists
- **Automated extraction**: AI-powered OCR converts workbook tables into practice material
- **Immediate practice**: Scan → Review → Practice workflow in minutes
- **Progress tracking**: Monitors mastery levels and practice history

### Target Audience
- Primary: 9th grade students (ages 14-15) at German Gymnasiums
- Secondary: Parents monitoring student progress
- Context: Students already have French workbooks with vocabulary tables

## Problem Statement

Students learning French in German Gymnasiums face several challenges:

1. **Manual entry burden**: Typing vocabulary lists from workbooks is time-consuming and error-prone
2. **Generic apps don't match curriculum**: Apps like Anki or Quizlet require manual setup and don't align with specific textbook content
3. **Motivation gap**: Students are more engaged when practicing their own materials
4. **Fragmented workflow**: Separate tools for vocabulary management and practice

### Solution
A unified web application that scans workbook pages, extracts vocabulary automatically, and provides immediate typing-based practice sessions with progress tracking.

## User Personas

### Primary Persona: Sophie (9th Grade Student)
- **Age**: 14 years old
- **Context**: Attends Gymnasium, learning French as second foreign language
- **Tech comfort**: High - uses iPad daily for schoolwork
- **Goals**: 
  - Prepare for upcoming vocabulary tests
  - Maintain daily practice routine
  - Avoid tedious manual list creation
- **Pain points**:
  - Limited study time due to multiple subjects
  - Loses motivation with generic vocabulary apps
  - Handwriting practice lists takes too long

### Secondary Persona: Parent/Guardian
- **Goals**: 
  - Monitor child's study consistency
  - Ensure practice aligns with school curriculum
  - Support learning without constant supervision
- **Needs**:
  - Progress visibility
  - Simple setup process
  - Reliable, safe platform

## Core Features & Requirements

### 1. User Authentication & Management

**Requirements:**
- Multi-user support with individual accounts
- Secure authentication using AWS Cognito
- OAuth2 flow with Cognito-hosted login UI
- User profile with basic statistics
- Password reset functionality
- Email verification on signup

**User Stories:**
- As a student, I want to create an account with my email so I can save my vocabulary lists
- As a student, I want to log in securely so my data remains private
- As a student, I want to reset my password if I forget it
- As a parent, I want to help my child set up their account safely

**Acceptance Criteria:**
- User can register with email and password
- Email verification required before first login
- Session persists across browser refreshes
- Logout clears all authentication tokens
- Failed login attempts are rate-limited

### 2. Image Upload & Processing

**Requirements:**
- Support common image formats: JPG, PNG, HEIC
- Maximum file size: 10MB per image
- Drag-and-drop interface for easy upload
- Alternative file picker for traditional upload
- Image preview before processing
- Processing status indicator with estimated time
- S3 storage with automatic lifecycle management (delete after 30 days)

**User Stories:**
- As a student, I want to drag and drop my workbook photo into the app
- As a student, I want to see a preview of my uploaded image to confirm it's correct
- As a student, I want to know when processing is complete
- As a student, I want clear error messages if my image is rejected

**Acceptance Criteria:**
- Upload accepts JPG, PNG, HEIC formats only
- File size validation occurs client-side before upload
- Upload progress bar shows percentage complete
- Processing status updates in real-time
- Clear error messages for unsupported formats or oversized files
- Images are compressed if over 5MB before storage

**Technical Notes:**
- Use S3 presigned URLs for direct browser-to-S3 upload
- Client-side image compression to optimize upload speed
- Store original image reference with vocabulary set metadata

### 3. Vocabulary Extraction & Review

**Requirements:**
- Automated OCR using AWS Textract with TABLE detection mode
- Fallback to OpenAI Vision API for challenging handwritten annotations
- Extract German-French vocabulary pairs from table structures
- Manual review interface before finalizing vocabulary set
- Editable table view with add/remove/modify capabilities
- Metadata fields: chapter number, page number, topic/title, date created
- Bulk operations: approve all, delete all, reprocess image

**User Stories:**
- As a student, I want the app to automatically find vocabulary tables in my workbook photo
- As a student, I want to review extracted vocabulary before it's saved
- As a student, I want to fix any OCR mistakes easily
- As a student, I want to add vocabulary pairs that were missed by the scanner
- As a student, I want to delete extracted words that aren't vocabulary (page headers, etc.)
- As a student, I want to organize vocabulary by chapter and topic

**Acceptance Criteria:**
- Extraction completes within 30 seconds for typical workbook page
- Review interface displays extracted pairs in editable table
- Each row can be edited inline (German and French columns)
- Add row button inserts new blank row
- Delete row button removes individual entries
- Chapter/page/topic fields are optional but recommended
- "Approve" button saves vocabulary set and enables practice
- "Reprocess" button triggers new extraction attempt
- Extraction confidence scores displayed per row (if below 80%, highlight for review)

**Edge Cases:**
- Multiple tables on one page: Extract all, separate by horizontal spacing
- Mixed content (exercises + vocabulary): Extract only table-structured content
- Handwritten annotations: Flag for manual review, attempt extraction with OpenAI Vision
- Tilted/skewed images: Auto-rotate based on text orientation detection
- Poor image quality: Display warning suggesting retake if confidence < 50%

**Technical Notes:**
- Textract TABLE feature detects rows and columns
- Parse Textract JSON response to extract cell content
- Assume left column = German, right column = French
- Store confidence scores per extracted pair
- For handwritten text, use OpenAI Vision API with prompt: "Extract vocabulary pairs from this image. Format as German | French, one pair per line."

### 4. Vocabulary Organization & Management

**Requirements:**
- Dashboard view listing all vocabulary sets
- Each set displays: title, item count, creation date, last practiced date, mastery percentage
- Sort options: by date, by title, by mastery level
- Filter options: by chapter, by date range, by mastery status
- Search across all vocabulary sets
- Archive functionality (hide without deleting)
- Bulk delete for multiple sets
- Export vocabulary set as CSV or printable PDF

**User Stories:**
- As a student, I want to see all my vocabulary sets organized on one page
- As a student, I want to quickly find vocabulary from a specific chapter
- As a student, I want to archive old vocabulary I no longer need to practice
- As a student, I want to export vocabulary to share with classmates or print

**Acceptance Criteria:**
- Dashboard loads all sets within 2 seconds
- Vocabulary sets display as cards with key metadata
- Clicking a set opens detail view
- Search updates results in real-time
- Archive moves set to separate "Archived" tab
- Delete requires confirmation dialog
- Export generates formatted CSV with German, French, Notes columns

### 5. Practice Session Interface

**Requirements:**
- User selects vocabulary set to practice from dashboard
- Practice mode selection: German→French or French→German
- Question randomization within session
- Large, clear text input field for answer entry
- "Check Answer" button (keyboard shortcut: Enter)
- Immediate feedback: correct (green) or incorrect (red)
- Display correct answer after incorrect attempt
- "Next Question" button to continue
- Progress bar showing position in session
- Option to skip question (marks as incorrect)
- Session summary at completion: score, time taken, detailed results

**User Stories:**
- As a student, I want to practice typing French words when shown German
- As a student, I want to also practice typing German when shown French
- As a student, I want immediate feedback so I know if I'm correct
- As a student, I want to see the correct answer when I'm wrong so I can learn
- As a student, I want to see my score as I practice to track improvement
- As a student, I want a summary at the end showing what I got right and wrong

**Acceptance Criteria:**
- Practice session includes all items from selected vocabulary set
- Questions appear in random order each session
- User cannot proceed without answering or skipping
- Answer checking is case-insensitive
- Fuzzy matching accepts minor typos (Levenshtein distance ≤ 2 for words >5 chars)
- Accepts common variations (café = cafe, naïve = naive)
- Correct answers show green checkmark
- Incorrect answers show red X and display correct answer
- Progress bar updates after each question
- Session summary displays: total score (X/Y), percentage, time elapsed
- Summary includes list of all questions with user's answer vs. correct answer

**Answer Validation Logic:**
- Normalize answers: trim whitespace, lowercase
- Accept articles with or without (der/die/das for German, le/la/les for French)
- Accept accented and non-accented characters as equivalent
- For compound answers (multiple correct options), accept any valid option
- Mark answer correct if fuzzy match score > 85%

**Technical Notes:**
- Use Levenshtein distance algorithm for fuzzy matching
- Frontend handles answer validation for instant feedback
- Backend records detailed results for progress tracking
- Session state stored in browser local storage to survive page refresh

### 6. Progress Tracking & Analytics

**Requirements:**
- Per-vocabulary-set statistics: mastery level, accuracy percentage, practice count
- Per-item tracking: correct attempts, incorrect attempts, last practiced date
- Mastery levels: 0 (never practiced) → 5 (consistently correct)
- Overall dashboard: total words learned, average accuracy, practice streak
- Visual progress indicators: bar charts, line graphs, heatmaps
- Practice history: calendar view showing practice days
- Detailed session history: list of past sessions with scores

**User Stories:**
- As a student, I want to see which words I've mastered
- As a student, I want to see which words I consistently get wrong
- As a student, I want to track my practice streak to stay motivated
- As a student, I want visual graphs showing my improvement over time
- As a parent, I want to see if my child is practicing regularly

**Acceptance Criteria:**
- Dashboard shows total vocabulary count and overall mastery percentage
- Each vocabulary set displays mastery level (0-100%)
- Item detail view shows per-word statistics
- Practice history calendar highlights days with completed sessions
- Graphs update after each practice session
- Mastery level increases after 3 consecutive correct answers
- Mastery level decreases after 2 consecutive incorrect answers

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

**Technical Notes:**
- Calculate statistics on-demand from practice session data
- Cache aggregate statistics in DynamoDB for performance
- Update cached stats after each completed session
- Use Chart.js or similar library for visualizations

### 7. User Interface & Experience

**Design Principles:**
- Clean, minimal, distraction-free
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

**Typography:**
- Headers: Inter or similar sans-serif (bold)
- Body: Inter regular
- Vocabulary display: Larger size (18-20px) for readability
- High contrast ratios for accessibility

**Layout:**
- Dashboard: Card-based grid layout
- Practice: Centered, single-column focus mode
- Review: Spreadsheet-style table view
- Navigation: Top bar with logo, user menu, main navigation links

**Responsive Breakpoints:**
- Mobile: < 640px (single column)
- Tablet: 640px - 1024px (2 columns)
- Desktop: > 1024px (3 columns on dashboard)

**Loading States:**
- Skeleton loaders for content
- Spinner for processing operations
- Progress bars for uploads and extractions

**Error Handling:**
- Toast notifications for transient errors
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
- Images stored in private S3 bucket with presigned URLs
- User data encrypted at rest (DynamoDB encryption)
- TLS 1.3 for all data in transit
- CORS properly configured for frontend domain only
- Input validation on all user-submitted data
- Rate limiting on API endpoints (100 requests/minute per user)
- SQL injection protection (use parameterized queries)
- XSS protection (sanitize user input)

### Scalability
- Support up to 1000 concurrent users
- Handle 10,000 vocabulary sets total
- Process 100 images per hour
- Store up to 100,000 practice session records
- DynamoDB auto-scaling enabled
- Lambda concurrency limits configured

### Availability
- 99.5% uptime target
- Graceful degradation if OCR service unavailable
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
- Sufficient color contrast ratios
- Focus indicators on interactive elements
- Alt text for all images
- ARIA labels where appropriate

## Data Privacy & Compliance

### Data Collection
- Email address (required for account)
- Display name (optional)
- Uploaded workbook images (stored 30 days)
- Extracted vocabulary data
- Practice session results
- Usage analytics (anonymized)

### Data Retention
- User accounts: Retained until user deletion request
- Vocabulary sets: Retained until user deletion
- Uploaded images: Auto-deleted after 30 days
- Practice sessions: Retained indefinitely (for progress tracking)
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

## Success Metrics

### User Engagement
- Daily active users (DAU)
- Weekly active users (WAU)
- Average session duration
- Practice sessions per week per user
- Vocabulary sets created per user
- User retention rate (7-day, 30-day)

### Feature Adoption
- Percentage of users who upload at least one image
- Percentage of extractions that are approved without edits
- Average edit count per vocabulary review
- Most used practice mode (German→French vs French→German)

### Learning Outcomes
- Average mastery level progression over time
- Average accuracy improvement over 30 days
- Vocabulary retention rate (tested via re-practice after 7 days)
- Practice streak length distribution

### Technical Performance
- API response time (p50, p95, p99)
- Image upload success rate
- Extraction accuracy rate (measured by user edit frequency)
- Error rate by endpoint
- Frontend page load times

## Future Enhancements (Out of Scope for MVP)

### Phase 2 Features
- Spaced repetition algorithm (smart scheduling)
- Audio pronunciation for French words (text-to-speech)
- Multiple choice practice mode
- Collaborative vocabulary sharing between students
- Teacher dashboard for classroom management
- Mobile native apps (iOS, Android)

### Phase 3 Features
- Gamification: points, badges, leaderboards
- Study reminders via email or push notifications
- Integration with popular textbook publishers
- Support for additional language pairs (Spanish, Latin, English)
- Handwriting input for iPad (using Apple Pencil)
- Vocabulary generation from any text (not just tables)

## Constraints & Assumptions

### Assumptions
- Students have access to iPad, laptop, or desktop browser
- Workbook pages contain structured vocabulary tables
- Students are motivated to use digital tools for studying
- Internet connection available during study sessions
- Vocabulary workbooks use standard Roman alphabet (no Cyrillic, Arabic, etc.)

### Constraints
- Budget: Optimize for low AWS costs (target <$50/month for 100 users)
- Time: MVP delivery in 4-6 weeks
- Team: Small development team (1-2 developers)
- Technical: Must use AWS services for all infrastructure
- Language: Initial support for German↔French only

### Known Limitations
- OCR accuracy depends on image quality (requires good lighting, focus)
- Handwritten annotations may not extract reliably
- No offline mode (requires internet connection)
- Limited to vocabulary tables (cannot extract from prose text)
- No real-time collaboration features

## Glossary

- **Vocabulary Set**: A collection of German-French word pairs extracted from a single workbook page or manually created
- **Practice Session**: A timed quiz where users type answers to vocabulary questions
- **Mastery Level**: A 0-5 scale indicating how well a user knows a vocabulary item
- **Extraction**: The automated OCR process that converts workbook images into structured vocabulary data
- **Review Interface**: The editable table view where users verify and correct extracted vocabulary
- **Fuzzy Matching**: Approximate string matching that accepts minor typos as correct
- **Gymnasium**: German secondary school (grades 5-12/13) preparing students for university

## Appendix: User Flow Diagrams

### Primary Flow: Scan to Practice
1. User uploads workbook image via drag-and-drop
2. System displays upload progress
3. System triggers OCR extraction (Textract)
4. System parses extraction results into German-French pairs
5. User reviews extracted vocabulary in editable table
6. User corrects any OCR errors
7. User adds metadata (chapter, topic)
8. User clicks "Approve" to save vocabulary set
9. User clicks "Start Practice" from dashboard
10. User selects practice direction (German→French or reverse)
11. System displays first question
12. User types answer and presses Enter
13. System validates answer and shows feedback
14. User proceeds to next question
15. System displays session summary at completion
16. System updates progress statistics

### Secondary Flow: Browse and Manage
1. User views dashboard with all vocabulary sets
2. User searches or filters for specific set
3. User clicks on vocabulary set card
4. User views detailed statistics for that set
5. User optionally edits vocabulary items
6. User archives or deletes set if needed

### Error Flow: Failed Extraction
1. User uploads image
2. System attempts extraction
3. Extraction fails or returns low confidence results
4. System displays error message with retry option
5. User retakes photo with better lighting/angle
6. User retries upload
7. If extraction still fails, user enters vocabulary manually

## Open Questions

1. Should there be a time limit per practice question, or allow unlimited time?
2. Should the app support collaborative features (sharing vocabulary sets between classmates)?
3. How should compound words be handled (German: "der Tisch" vs "Tisch")?
4. Should there be a mobile app in addition to web, or web-only for MVP?
5. What level of parental controls or monitoring is needed?
6. Should practice sessions be resumable if interrupted?
7. How to handle vocabulary with multiple correct translations?