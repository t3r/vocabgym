/**
 * Learning-goal status → Tailwind class / German label helpers.
 *
 * The exact same status→color switches and status→label maps were duplicated
 * across GoalBanner.vue and GoalDetailView.vue (once per visual context). This
 * centralises them WITHOUT changing any rendered class string: each "variant"
 * below reproduces the original branch outputs byte-for-byte, including the
 * per-variant default (some defaulted to primary, others to gray).
 *
 * Colour keys: on_track & completed → green, at_risk → yellow, behind → red.
 * Everything else (incl. expired / undefined) → the variant's `default`.
 */

const VARIANTS = {
  // GoalBanner: outer banner box
  banner: {
    green: 'bg-green-50 border-green-300 dark:bg-green-900/20 dark:border-green-700',
    yellow: 'bg-yellow-50 border-yellow-300 dark:bg-yellow-900/20 dark:border-yellow-700',
    red: 'bg-red-50 border-red-300 dark:bg-red-900/20 dark:border-red-700',
    default: 'bg-gray-50 border-gray-300 dark:bg-gray-800 dark:border-gray-700',
  },
  // GoalBanner: title text
  title: {
    green: 'text-green-800 dark:text-green-200',
    yellow: 'text-yellow-800 dark:text-yellow-200',
    red: 'text-red-800 dark:text-red-200',
    default: 'text-gray-800 dark:text-gray-200',
  },
  // GoalBanner: meta / recommendation text
  meta: {
    green: 'text-green-700 dark:text-green-300',
    yellow: 'text-yellow-700 dark:text-yellow-300',
    red: 'text-red-700 dark:text-red-300',
    default: 'text-gray-600 dark:text-gray-400',
  },
  // GoalBanner: "Details →" link
  link: {
    green: 'text-green-700 dark:text-green-300',
    yellow: 'text-yellow-700 dark:text-yellow-300',
    red: 'text-red-700 dark:text-red-300',
    default: 'text-primary-600 dark:text-primary-400',
  },
  // Progress bar fill (GoalBanner + GoalDetailView, identical)
  bar: {
    green: 'bg-green-500 dark:bg-green-400',
    yellow: 'bg-yellow-500 dark:bg-yellow-400',
    red: 'bg-red-500 dark:bg-red-400',
    default: 'bg-primary-500 dark:bg-primary-400',
  },
  // GoalDetailView: big progress % text
  text: {
    green: 'text-green-600 dark:text-green-400',
    yellow: 'text-yellow-600 dark:text-yellow-400',
    red: 'text-red-600 dark:text-red-400',
    default: 'text-primary-600 dark:text-primary-400',
  },
  // GoalDetailView: status pill / badge
  badge: {
    green: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
    yellow: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
    red: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
    default: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300',
  },
  // GoalDetailView: recommendation box
  recommendation: {
    green: 'bg-green-50 border-green-300 text-green-800 dark:bg-green-900/20 dark:border-green-700 dark:text-green-200',
    yellow: 'bg-yellow-50 border-yellow-300 text-yellow-800 dark:bg-yellow-900/20 dark:border-yellow-700 dark:text-yellow-200',
    red: 'bg-red-50 border-red-300 text-red-800 dark:bg-red-900/20 dark:border-red-700 dark:text-red-200',
    default: 'bg-gray-50 border-gray-300 text-gray-700 dark:bg-gray-800 dark:border-gray-700 dark:text-gray-300',
  },
  // GoalDetailView: member progress bar (default is gray-400/500, not primary)
  memberBar: {
    green: 'bg-green-500 dark:bg-green-400',
    yellow: 'bg-yellow-500 dark:bg-yellow-400',
    red: 'bg-red-500 dark:bg-red-400',
    default: 'bg-gray-400 dark:bg-gray-500',
  },
}

function colourKey(status) {
  switch (status) {
    case 'on_track':
    case 'completed':
      return 'green'
    case 'at_risk':
      return 'yellow'
    case 'behind':
      return 'red'
    default:
      return 'default'
  }
}

/**
 * Return the Tailwind class string for a given visual `variant` and goal
 * `status`. Output is identical to the original per-file switch statements.
 */
export function goalStatusClass(variant, status) {
  const map = VARIANTS[variant]
  if (!map) return ''
  return map[colourKey(status)]
}

const STATUS_LABELS = {
  on_track: 'Im Zeitplan',
  at_risk: 'Gefährdet',
  behind: 'Im Rückstand',
  completed: 'Abgeschlossen',
  expired: 'Abgelaufen',
}

/** German label for a goal status (empty string when unknown). */
export function goalStatusLabel(status) {
  return STATUS_LABELS[status] || status || ''
}
