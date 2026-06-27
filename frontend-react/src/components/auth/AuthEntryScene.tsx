import { useState } from 'react'
import { LoginPage } from '../../pages/LoginPage'
import { RegisterPage } from '../../pages/RegisterPage'

export function AuthEntryScene() {
  const [view, setView] = useState<'login' | 'register'>('login')
  const [phase, setPhase] = useState<'home' | 'auth'>('home')

  const openAuth = (next: 'login' | 'register' = 'login') => {
    setView(next)
    setPhase('auth')
  }

  const returnHome = () => {
    setView('login')
    setPhase('home')
  }

  if (view === 'register') {
    return (
      <RegisterPage
        phase={phase}
        onOpenAuth={() => openAuth('register')}
        onNavigate={() => setView('login')}
        onReturnHome={returnHome}
      />
    )
  }

  return (
    <LoginPage
      phase={phase}
      onOpenAuth={() => openAuth('login')}
      onNavigate={() => setView('register')}
      onReturnHome={returnHome}
    />
  )
}
