import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LandingView from '@/views/LandingView.vue'

const routes = [
  {
    path: '/',
    name: 'Landing',
    component: LandingView,
    meta: { requiresAuth: false, title: 'Willkommen' }
  },
  {
    path: '/callback',
    name: 'Callback',
    component: () => import('@/views/CallbackView.vue'),
    meta: { requiresAuth: false, title: 'Anmeldung...' }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/views/DashboardView.vue'),
    meta: { requiresAuth: true, title: 'Dashboard' }
  },
  {
    path: '/upload',
    name: 'Upload',
    component: () => import('@/views/UploadView.vue'),
    meta: { requiresAuth: true, title: 'Bild hochladen' }
  },
  {
    path: '/review/:vocabSetId',
    name: 'Review',
    component: () => import('@/views/ReviewView.vue'),
    meta: { requiresAuth: true, title: 'Vokabeln prüfen' },
    props: true
  },
  {
    path: '/practice/:vocabSetId',
    name: 'Practice',
    component: () => import('@/views/PracticeView.vue'),
    meta: { requiresAuth: true, title: 'Üben' },
    props: true
  },
  {
    path: '/progress',
    name: 'Progress',
    component: () => import('@/views/ProgressView.vue'),
    meta: { requiresAuth: true, title: 'Fortschritt' }
  },
  {
    path: '/vocab/:vocabSetId',
    name: 'VocabSetDetail',
    component: () => import('@/views/VocabSetDetailView.vue'),
    meta: { requiresAuth: true, title: 'Vokabelset' },
    props: true
  },
  {
    path: '/invite/:token',
    name: 'Invite',
    component: () => import('@/views/InviteView.vue'),
    meta: { requiresAuth: false, title: 'Einladung' },
    props: true
  },
  {
    path: '/goals/:goalId',
    name: 'GoalDetail',
    component: () => import('@/views/GoalDetailView.vue'),
    props: true,
    meta: { requiresAuth: true, title: 'Lernziel' }
  },
  {
    path: '/league',
    name: 'League',
    component: () => import('@/views/LeagueView.vue'),
    meta: { requiresAuth: true, title: 'Liga' }
  },
  {
    path: '/league/join/:code?',
    name: 'LeagueJoin',
    component: () => import('@/views/LeagueJoinView.vue'),
    meta: { requiresAuth: true, title: 'Liga beitreten' },
    props: true
  },
  {
    path: '/help',
    name: 'Help',
    component: () => import('@/views/HelpView.vue'),
    meta: { requiresAuth: false, title: 'Hilfe' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { requiresAuth: false, title: 'Nicht gefunden' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // Update document title
  document.title = to.meta.title
    ? `${to.meta.title} - VocabTrainer`
    : 'VocabTrainer'

  // Public routes - allow access
  if (!to.meta.requiresAuth) {
    // If authenticated and visiting landing, redirect to dashboard
    if (to.name === 'Landing' && authStore.isAuthenticated) {
      return next({ name: 'Dashboard' })
    }
    return next()
  }

  // Protected routes - check authentication
  if (!authStore.isAuthenticated) {
    authStore.login()
    return
  }

  next()
})

export default router
