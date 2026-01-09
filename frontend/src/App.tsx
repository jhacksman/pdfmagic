import { useState, useCallback, useEffect } from 'react'
import './App.css'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { FileText, Merge, Split, Minimize2, Image, Upload, LogOut, User, Check, Zap, Crown, Settings, Trash2, KeyRound, BarChart3, Gift, Copy } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''
const APPLE_CLIENT_ID = import.meta.env.VITE_APPLE_CLIENT_ID || ''

interface UserData {
  id: number
  email: string
  tier: string
  daily_ops_remaining: number
  max_file_mb: number
}

interface PricingTier {
  name: string
  price: number
  price_id?: string
  features: string[]
}

function App() {
  const [user, setUser] = useState<UserData | null>(null)
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [authDialogOpen, setAuthDialogOpen] = useState(false)
  const [selectedTool, setSelectedTool] = useState<string>('merge')
  const [files, setFiles] = useState<File[]>([])
  const [processing, setProcessing] = useState(false)
  const [message, setMessage] = useState('')
    const [pricing, setPricing] = useState<PricingTier[]>([])
    const [showPricing, setShowPricing] = useState(false)
    const [showForgotPassword, setShowForgotPassword] = useState(false)
    const [forgotPasswordEmail, setForgotPasswordEmail] = useState('')
    const [forgotPasswordMessage, setForgotPasswordMessage] = useState('')
    const [showResetPassword, setShowResetPassword] = useState(false)
    const [resetToken, setResetToken] = useState('')
    const [newPassword, setNewPassword] = useState('')
    const [resetPasswordMessage, setResetPasswordMessage] = useState('')
    const [showProfile, setShowProfile] = useState(false)
    const [profileEmail, setProfileEmail] = useState('')
    const [currentPassword, setCurrentPassword] = useState('')
    const [profileNewPassword, setProfileNewPassword] = useState('')
    const [profileMessage, setProfileMessage] = useState('')
        const [showTerms, setShowTerms] = useState(false)
        const [showPrivacy, setShowPrivacy] = useState(false)
        const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
        // Phase 2: Analytics and Referral
        const [showAnalytics, setShowAnalytics] = useState(false)
        const [showReferral, setShowReferral] = useState(false)
        const [analyticsData, setAnalyticsData] = useState<{
          total_operations: number
          operations_by_type: Record<string, number>
          referral_code: string
          referred_users: number
          total_rewards: number
          tier: string
        } | null>(null)
        const [referralData, setReferralData] = useState<{
          referral_code: string
          referral_url: string
          referred_users: number
          converted_users: number
          total_rewards: number
          pending_rewards: number
        } | null>(null)
        const [referralCopied, setReferralCopied] = useState(false)

  const fetchUser = useCallback(async () => {
    if (!token) return
    try {
      const res = await fetch(`${API_URL}/api/user/me`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (res.ok) {
        const data = await res.json()
        setUser(data)
      } else {
        localStorage.removeItem('token')
        setToken(null)
        setUser(null)
      }
    } catch (e) {
      console.error('Failed to fetch user', e)
    }
  }, [token])

  const fetchPricing = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/pricing`)
      if (res.ok) {
        const data = await res.json()
        setPricing(data.tiers)
      }
    } catch (e) {
      console.error('Failed to fetch pricing', e)
    }
  }, [])

  useEffect(() => {
    fetchUser()
    fetchPricing()
  }, [fetchUser, fetchPricing])

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError('')
    try {
      const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register'
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword })
      })
      const data = await res.json()
      if (res.ok) {
        localStorage.setItem('token', data.access_token)
        setToken(data.access_token)
        setAuthDialogOpen(false)
        setAuthEmail('')
        setAuthPassword('')
      } else {
        setAuthError(data.detail || 'Authentication failed')
      }
      } catch {
        setAuthError('Network error. Please try again.')
      }
    }

      const handleLogout = () => {
      localStorage.removeItem('token')
      setToken(null)
      setUser(null)
    }

    const handleGoogleAuth = async (googleToken: string) => {
      setAuthError('')
      try {
        const res = await fetch(`${API_URL}/api/auth/google`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_token: googleToken })
        })
        const data = await res.json()
        if (res.ok) {
          localStorage.setItem('token', data.access_token)
          setToken(data.access_token)
          setAuthDialogOpen(false)
        } else {
          setAuthError(data.detail || 'Google authentication failed')
        }
          } catch {
            setAuthError('Network error. Please try again.')
          }
        }

        const handleAppleAuth = async (appleToken: string, userInfo?: { email?: string }) => {
      setAuthError('')
      try {
        const res = await fetch(`${API_URL}/api/auth/apple`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id_token: appleToken, user_info: userInfo })
        })
        const data = await res.json()
        if (res.ok) {
          localStorage.setItem('token', data.access_token)
          setToken(data.access_token)
          setAuthDialogOpen(false)
        } else {
          setAuthError(data.detail || 'Apple authentication failed')
        }
          } catch {
            setAuthError('Network error. Please try again.')
          }
        }

        const initGoogleSignIn = () => {
      if (!GOOGLE_CLIENT_ID) {
        setAuthError('Google Sign-In not configured')
        return
      }
      // Load Google Identity Services
      const script = document.createElement('script')
      script.src = 'https://accounts.google.com/gsi/client'
      script.async = true
      script.defer = true
      script.onload = () => {
        // @ts-expect-error Google Identity Services
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response: { credential: string }) => {
            handleGoogleAuth(response.credential)
          }
        })
        // @ts-expect-error Google Identity Services
        window.google.accounts.id.prompt()
      }
      document.body.appendChild(script)
    }

    const initAppleSignIn = () => {
      if (!APPLE_CLIENT_ID) {
        setAuthError('Apple Sign-In not configured')
        return
      }
      // Load Apple Sign-In JS
      const script = document.createElement('script')
      script.src = 'https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js'
      script.async = true
      script.defer = true
      script.onload = () => {
        // @ts-expect-error Apple Sign-In
        window.AppleID.auth.init({
          clientId: APPLE_CLIENT_ID,
          scope: 'email name',
          redirectURI: window.location.origin,
          usePopup: true
        })
        // @ts-expect-error Apple Sign-In
        window.AppleID.auth.signIn().then((response: { authorization: { id_token: string }, user?: { email?: string } }) => {
          handleAppleAuth(response.authorization.id_token, response.user)
        }).catch((error: Error) => {
          if (error.message !== 'popup_closed_by_user') {
            setAuthError('Apple Sign-In failed')
          }
        })
      }
      document.body.appendChild(script)
    }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files))
      setMessage('')
    }
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    if (e.dataTransfer.files) {
      setFiles(Array.from(e.dataTransfer.files))
      setMessage('')
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  const processFiles = async () => {
    if (!token || !user) {
      setAuthDialogOpen(true)
      return
    }
    if (files.length === 0) {
      setMessage('Please select files first')
      return
    }

    setProcessing(true)
    setMessage('')

    const formData = new FormData()
    
    let endpoint = ''
    switch (selectedTool) {
      case 'merge':
        if (files.length < 2) {
          setMessage('Please select at least 2 PDF files to merge')
          setProcessing(false)
          return
        }
        endpoint = '/api/pdf/merge'
        files.forEach(f => formData.append('files', f))
        break
      case 'split':
        if (files.length !== 1) {
          setMessage('Please select exactly 1 PDF file to split')
          setProcessing(false)
          return
        }
        endpoint = '/api/pdf/split'
        formData.append('file', files[0])
        break
      case 'compress':
        if (files.length !== 1) {
          setMessage('Please select exactly 1 PDF file to compress')
          setProcessing(false)
          return
        }
        endpoint = '/api/pdf/compress'
        formData.append('file', files[0])
        break
      case 'pdf-to-images':
        if (files.length !== 1) {
          setMessage('Please select exactly 1 PDF file')
          setProcessing(false)
          return
        }
        endpoint = '/api/pdf/to-images'
        formData.append('file', files[0])
        break
      case 'images-to-pdf':
        if (files.length < 1) {
          setMessage('Please select at least 1 image file')
          setProcessing(false)
          return
        }
        endpoint = '/api/images/to-pdf'
        files.forEach(f => formData.append('files', f))
        break
    }

    try {
      const res = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: formData
      })

      if (res.ok) {
        const blob = await res.blob()
        const contentDisposition = res.headers.get('Content-Disposition')
        let filename = 'download'
        if (contentDisposition) {
          const match = contentDisposition.match(/filename=(.+)/)
          if (match) filename = match[1]
        }
        
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
        
        setMessage('Success! Your file has been downloaded.')
        setFiles([])
        fetchUser() // Refresh user data to update remaining ops
      } else {
        const data = await res.json()
        setMessage(data.detail || 'Processing failed')
      }
      } catch {
        setMessage('Network error. Please try again.')
      } finally {
        setProcessing(false)
      }
    }

    const handleUpgrade = async (priceId: string) => {
    if (!token) {
      setAuthDialogOpen(true)
      return
    }
    try {
      const res = await fetch(`${API_URL}/api/stripe/create-checkout`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          price_id: priceId,
          success_url: window.location.origin + '?success=true',
          cancel_url: window.location.origin + '?canceled=true'
        })
      })
      const data = await res.json()
      if (res.ok && data.checkout_url) {
        window.location.href = data.checkout_url
      } else {
        setMessage(data.detail || 'Failed to create checkout session')
      }
      } catch {
        setMessage('Network error. Please try again.')
      }
    }

      const handleManageSubscription = async () => {
      if (!token) return
      try {
        const res = await fetch(`${API_URL}/api/stripe/portal`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` }
        })
        const data = await res.json()
        if (res.ok && data.portal_url) {
          window.location.href = data.portal_url
        }
          } catch (err) {
            console.error('Failed to open portal', err)
          }
        }

        const handleForgotPassword = async (e: React.FormEvent) => {
      e.preventDefault()
      setForgotPasswordMessage('')
      try {
        const res = await fetch(`${API_URL}/api/auth/forgot-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: forgotPasswordEmail })
        })
        const data = await res.json()
        setForgotPasswordMessage(data.message || 'Check your email for reset instructions.')
          } catch {
            setForgotPasswordMessage('Network error. Please try again.')
          }
        }

        const handleResetPassword = async (e: React.FormEvent) => {
      e.preventDefault()
      setResetPasswordMessage('')
      try {
        const res = await fetch(`${API_URL}/api/auth/reset-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: resetToken, new_password: newPassword })
        })
        const data = await res.json()
        if (res.ok) {
          setResetPasswordMessage('Password reset successfully! You can now sign in.')
          setNewPassword('')
          setResetToken('')
        } else {
          setResetPasswordMessage(data.detail || 'Failed to reset password.')
        }
          } catch {
            setResetPasswordMessage('Network error. Please try again.')
          }
        }

        const handleUpdateProfile = async (e: React.FormEvent) => {
      e.preventDefault()
      setProfileMessage('')
      try {
        const body: { email?: string; current_password?: string; new_password?: string } = {}
        if (profileEmail && profileEmail !== user?.email) body.email = profileEmail
        if (profileNewPassword) {
          body.current_password = currentPassword
          body.new_password = profileNewPassword
        }
      
        if (Object.keys(body).length === 0) {
          setProfileMessage('No changes to save.')
          return
        }

        const res = await fetch(`${API_URL}/api/user/profile`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify(body)
        })
        const data = await res.json()
        if (res.ok) {
          setProfileMessage('Profile updated successfully!')
          setCurrentPassword('')
          setProfileNewPassword('')
          fetchUser()
        } else {
          setProfileMessage(data.detail || 'Failed to update profile.')
        }
          } catch {
            setProfileMessage('Network error. Please try again.')
          }
        }

              const handleDeleteAccount = async () => {
            try {
              const res = await fetch(`${API_URL}/api/user/account`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${token}` }
              })
              if (res.ok) {
                localStorage.removeItem('token')
                setToken(null)
                setUser(null)
                setShowDeleteConfirm(false)
                setShowProfile(false)
              }
                } catch (err) {
                  console.error('Failed to delete account', err)
                }
              }

          // Phase 2: Analytics and Referral handlers
          const fetchAnalytics = async () => {
            if (!token) return
            try {
              const res = await fetch(`${API_URL}/api/analytics/dashboard`, {
                headers: { Authorization: `Bearer ${token}` }
              })
              if (res.ok) {
                const data = await res.json()
                setAnalyticsData(data)
              }
            } catch (err) {
              console.error('Failed to fetch analytics', err)
            }
          }

          const fetchReferralData = async () => {
            if (!token) return
            try {
              const [codeRes, statsRes] = await Promise.all([
                fetch(`${API_URL}/api/referral/code`, {
                  headers: { Authorization: `Bearer ${token}` }
                }),
                fetch(`${API_URL}/api/referral/stats`, {
                  headers: { Authorization: `Bearer ${token}` }
                })
              ])
              if (codeRes.ok && statsRes.ok) {
                const codeData = await codeRes.json()
                const statsData = await statsRes.json()
                setReferralData({
                  referral_code: codeData.referral_code,
                  referral_url: codeData.referral_url,
                  referred_users: statsData.referred_users,
                  converted_users: statsData.converted_users,
                  total_rewards: statsData.total_rewards,
                  pending_rewards: statsData.pending_rewards
                })
              }
            } catch (err) {
              console.error('Failed to fetch referral data', err)
            }
          }

          const copyReferralLink = () => {
            if (referralData?.referral_url) {
              navigator.clipboard.writeText(referralData.referral_url)
              setReferralCopied(true)
              setTimeout(() => setReferralCopied(false), 2000)
            }
          }

              // Check for reset token in URL
    useEffect(() => {
      const params = new URLSearchParams(window.location.search)
      const token = params.get('token')
      if (token) {
        setResetToken(token)
        setShowResetPassword(true)
        window.history.replaceState({}, '', window.location.pathname)
      }
    }, [])

    // Initialize profile email when user loads
    useEffect(() => {
      if (user) {
        setProfileEmail(user.email)
      }
    }, [user])

    const tools = [
    { id: 'merge', name: 'Merge PDFs', icon: Merge, description: 'Combine multiple PDFs into one', accept: '.pdf', multiple: true },
    { id: 'split', name: 'Split PDF', icon: Split, description: 'Split a PDF into individual pages', accept: '.pdf', multiple: false },
    { id: 'compress', name: 'Compress PDF', icon: Minimize2, description: 'Reduce PDF file size', accept: '.pdf', multiple: false },
    { id: 'pdf-to-images', name: 'PDF to Images', icon: Image, description: 'Extract images from PDF', accept: '.pdf', multiple: false },
    { id: 'images-to-pdf', name: 'Images to PDF', icon: FileText, description: 'Convert images to PDF', accept: 'image/*', multiple: true },
  ]

  const currentTool = tools.find(t => t.id === selectedTool)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Header */}
      <header className="border-b border-white/10 bg-black/20 backdrop-blur-sm">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FileText className="h-8 w-8 text-purple-400" />
            <span className="text-2xl font-bold text-white">PDFMagic</span>
          </div>
          <div className="flex items-center gap-4">
            <Button variant="ghost" className="text-white hover:text-purple-300" onClick={() => setShowPricing(true)}>
              Pricing
            </Button>
            {user ? (
              <div className="flex items-center gap-4">
                <div className="text-sm text-white/70">
                  <span className="text-purple-300 font-medium">{user.tier.toUpperCase()}</span>
                  <span className="mx-2">|</span>
                  <span>{user.daily_ops_remaining} ops left today</span>
                </div>
                                {user.tier !== 'free' && (
                                  <Button variant="outline" size="sm" onClick={handleManageSubscription} className="border-white/20 text-white hover:bg-white/10">
                                    Manage Subscription
                                  </Button>
                                )}
                                                                <Button variant="ghost" size="sm" onClick={() => { setShowAnalytics(true); fetchAnalytics(); }} className="text-white hover:text-purple-300">
                                                                  <BarChart3 className="h-4 w-4 mr-2" />
                                                                  Analytics
                                                                </Button>
                                                                <Button variant="ghost" size="sm" onClick={() => { setShowReferral(true); fetchReferralData(); }} className="text-white hover:text-purple-300">
                                                                  <Gift className="h-4 w-4 mr-2" />
                                                                  Referral
                                                                </Button>
                                                                <Button variant="ghost" size="sm" onClick={() => setShowProfile(true)} className="text-white hover:text-purple-300">
                                                                  <Settings className="h-4 w-4 mr-2" />
                                                                  Profile
                                                                </Button>
                                                                <Button variant="ghost" size="sm" onClick={handleLogout} className="text-white hover:text-red-300">
                                                                  <LogOut className="h-4 w-4 mr-2" />
                                                                  Logout
                                                                </Button>
              </div>
            ) : (
              <Dialog open={authDialogOpen} onOpenChange={setAuthDialogOpen}>
                <DialogTrigger asChild>
                  <Button className="bg-purple-600 hover:bg-purple-700 text-white">
                    <User className="h-4 w-4 mr-2" />
                    Sign In
                  </Button>
                </DialogTrigger>
                <DialogContent className="bg-slate-900 border-white/10 text-white">
                  <DialogHeader>
                    <DialogTitle>{authMode === 'login' ? 'Sign In' : 'Create Account'}</DialogTitle>
                  </DialogHeader>
                  <form onSubmit={handleAuth} className="space-y-4">
                    <div>
                      <Label htmlFor="email">Email</Label>
                      <Input
                        id="email"
                        type="email"
                        value={authEmail}
                        onChange={(e) => setAuthEmail(e.target.value)}
                        className="bg-slate-800 border-white/20 text-white"
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="password">Password</Label>
                      <Input
                        id="password"
                        type="password"
                        value={authPassword}
                        onChange={(e) => setAuthPassword(e.target.value)}
                        className="bg-slate-800 border-white/20 text-white"
                        required
                      />
                    </div>
                                      {authError && <p className="text-red-400 text-sm">{authError}</p>}
                                      <Button type="submit" className="w-full bg-purple-600 hover:bg-purple-700">
                                        {authMode === 'login' ? 'Sign In' : 'Create Account'}
                                      </Button>
                    
                                      <div className="relative my-4">
                                        <div className="absolute inset-0 flex items-center">
                                          <span className="w-full border-t border-white/20" />
                                        </div>
                                        <div className="relative flex justify-center text-xs uppercase">
                                          <span className="bg-slate-900 px-2 text-white/50">Or continue with</span>
                                        </div>
                                      </div>
                    
                                                                            <div className="grid grid-cols-2 gap-3">
                                                                              <Button
                                                                                type="button"
                                                                                variant="outline"
                                                                                className="border-white/20 bg-white text-slate-900 hover:bg-gray-100"
                                                                                onClick={initGoogleSignIn}
                                                                              >
                                                                                <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24">
                                                                                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                                                                                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                                                                                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                                                                                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                                                                                </svg>
                                                                                Google
                                                                              </Button>
                                                                              <Button
                                                                                type="button"
                                                                                variant="outline"
                                                                                className="border-white/20 bg-black text-white hover:bg-gray-900"
                                                                                onClick={initAppleSignIn}
                                                                              >
                                                                                <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24" fill="currentColor">
                                                                                  <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.81-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
                                                                                </svg>
                                                                                Apple
                                                                              </Button>
                                                                            </div>
                    
                                                                          {authMode === 'login' && (
                                                                            <p className="text-center text-sm">
                                                                              <button
                                                                                type="button"
                                                                                className="text-purple-400 hover:underline"
                                                                                onClick={() => { setAuthDialogOpen(false); setShowForgotPassword(true); }}
                                                                              >
                                                                                Forgot your password?
                                                                              </button>
                                                                            </p>
                                                                          )}
                                                                          <p className="text-center text-sm text-white/60 mt-4">
                                                                            {authMode === 'login' ? "Don't have an account? " : "Already have an account? "}
                                                                            <button
                                                                              type="button"
                                                                              className="text-purple-400 hover:underline"
                                                                              onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
                                                                            >
                                                                              {authMode === 'login' ? 'Sign up' : 'Sign in'}
                                                                            </button>
                                                                          </p>
                                                                        </form>
                </DialogContent>
              </Dialog>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-16 text-center">
        <h1 className="text-5xl font-bold text-white mb-4">
          All Your PDF Tools in One Place
        </h1>
        <p className="text-xl text-white/70 mb-8 max-w-2xl mx-auto">
          Merge, split, compress, and convert PDFs with ease. Fast, secure, and free to start.
        </p>
      </section>

      {/* Tools Section */}
      <section className="container mx-auto px-4 pb-16">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          {tools.map((tool) => (
            <button
              key={tool.id}
              onClick={() => { setSelectedTool(tool.id); setFiles([]); setMessage(''); }}
              className={`p-4 rounded-xl border transition-all ${
                selectedTool === tool.id
                  ? 'bg-purple-600 border-purple-400 text-white'
                  : 'bg-white/5 border-white/10 text-white/70 hover:bg-white/10 hover:text-white'
              }`}
            >
              <tool.icon className="h-8 w-8 mx-auto mb-2" />
              <span className="text-sm font-medium">{tool.name}</span>
            </button>
          ))}
        </div>

        {/* Upload Area */}
        <Card className="bg-white/5 border-white/10 p-8">
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            className="border-2 border-dashed border-white/20 rounded-xl p-12 text-center hover:border-purple-400 transition-colors cursor-pointer"
            onClick={() => document.getElementById('file-input')?.click()}
          >
            <Upload className="h-12 w-12 text-white/40 mx-auto mb-4" />
            <p className="text-white text-lg mb-2">
              {currentTool?.description}
            </p>
            <p className="text-white/50 text-sm mb-4">
              Drag and drop files here, or click to browse
            </p>
            <input
              id="file-input"
              type="file"
              accept={currentTool?.accept}
              multiple={currentTool?.multiple}
              onChange={handleFileChange}
              className="hidden"
            />
            {files.length > 0 && (
              <div className="mt-4 space-y-2">
                {files.map((file, i) => (
                  <div key={i} className="text-purple-300 text-sm">
                    {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
                  </div>
                ))}
              </div>
            )}
          </div>

          {message && (
            <p className={`mt-4 text-center ${message.includes('Success') ? 'text-green-400' : 'text-red-400'}`}>
              {message}
            </p>
          )}

          <div className="mt-6 flex justify-center">
            <Button
              onClick={processFiles}
              disabled={processing || files.length === 0}
              className="bg-purple-600 hover:bg-purple-700 text-white px-8 py-6 text-lg"
            >
              {processing ? 'Processing...' : `Process ${files.length} File${files.length !== 1 ? 's' : ''}`}
            </Button>
          </div>

          {user && (
            <p className="text-center text-white/50 text-sm mt-4">
              Max file size: {user.max_file_mb}MB | {user.daily_ops_remaining} operations remaining today
            </p>
          )}
        </Card>
      </section>

      {/* Pricing Modal */}
      <Dialog open={showPricing} onOpenChange={setShowPricing}>
        <DialogContent className="bg-slate-900 border-white/10 text-white max-w-4xl">
          <DialogHeader>
            <DialogTitle className="text-2xl text-center">Choose Your Plan</DialogTitle>
          </DialogHeader>
          <div className="grid md:grid-cols-3 gap-6 mt-6">
            {pricing.map((tier, i) => (
              <Card
                key={tier.name}
                className={`p-6 ${
                  i === 1
                    ? 'bg-purple-600/20 border-purple-400'
                    : 'bg-white/5 border-white/10'
                }`}
              >
                <div className="text-center mb-4">
                  {i === 0 && <Zap className="h-8 w-8 mx-auto mb-2 text-white/60" />}
                  {i === 1 && <Crown className="h-8 w-8 mx-auto mb-2 text-purple-400" />}
                  {i === 2 && <Crown className="h-8 w-8 mx-auto mb-2 text-yellow-400" />}
                  <h3 className="text-xl font-bold text-white">{tier.name}</h3>
                  <div className="text-3xl font-bold text-white mt-2">
                    ${tier.price}
                    {tier.price > 0 && <span className="text-sm font-normal text-white/60">/month</span>}
                  </div>
                </div>
                <ul className="space-y-3 mb-6">
                  {tier.features.map((feature, j) => (
                    <li key={j} className="flex items-center gap-2 text-white/80 text-sm">
                      <Check className="h-4 w-4 text-green-400 flex-shrink-0" />
                      {feature}
                    </li>
                  ))}
                </ul>
                {tier.price_id && user?.tier !== tier.name.toLowerCase() ? (
                  <Button
                    onClick={() => handleUpgrade(tier.price_id!)}
                    className={`w-full ${
                      i === 1
                        ? 'bg-purple-600 hover:bg-purple-700'
                        : 'bg-white/10 hover:bg-white/20'
                    }`}
                  >
                    {user?.tier === 'free' ? 'Upgrade' : 'Switch Plan'}
                  </Button>
                ) : tier.price === 0 ? (
                  <Button variant="outline" className="w-full border-white/20 text-white" disabled>
                    {user?.tier === 'free' ? 'Current Plan' : 'Free Tier'}
                  </Button>
                ) : (
                  <Button variant="outline" className="w-full border-white/20 text-white" disabled>
                    Current Plan
                  </Button>
                )}
              </Card>
            ))}
          </div>
        </DialogContent>
      </Dialog>

      {/* Forgot Password Modal */}
      <Dialog open={showForgotPassword} onOpenChange={setShowForgotPassword}>
        <DialogContent className="bg-slate-900 border-white/10 text-white">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <KeyRound className="h-5 w-5" />
              Reset Password
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleForgotPassword} className="space-y-4">
            <p className="text-white/70 text-sm">Enter your email address and we'll send you a link to reset your password.</p>
            <div>
              <Label htmlFor="forgot-email">Email</Label>
              <Input
                id="forgot-email"
                type="email"
                value={forgotPasswordEmail}
                onChange={(e) => setForgotPasswordEmail(e.target.value)}
                className="bg-slate-800 border-white/20 text-white"
                required
              />
            </div>
            {forgotPasswordMessage && (
              <p className={`text-sm ${forgotPasswordMessage.includes('error') ? 'text-red-400' : 'text-green-400'}`}>
                {forgotPasswordMessage}
              </p>
            )}
            <Button type="submit" className="w-full bg-purple-600 hover:bg-purple-700">
              Send Reset Link
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      {/* Reset Password Modal */}
      <Dialog open={showResetPassword} onOpenChange={setShowResetPassword}>
        <DialogContent className="bg-slate-900 border-white/10 text-white">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <KeyRound className="h-5 w-5" />
              Set New Password
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleResetPassword} className="space-y-4">
            <div>
              <Label htmlFor="new-password">New Password</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="bg-slate-800 border-white/20 text-white"
                required
                minLength={6}
              />
            </div>
            {resetPasswordMessage && (
              <p className={`text-sm ${resetPasswordMessage.includes('successfully') ? 'text-green-400' : 'text-red-400'}`}>
                {resetPasswordMessage}
              </p>
            )}
            <Button type="submit" className="w-full bg-purple-600 hover:bg-purple-700">
              Reset Password
            </Button>
          </form>
        </DialogContent>
      </Dialog>

      {/* Profile Modal */}
      <Dialog open={showProfile} onOpenChange={setShowProfile}>
        <DialogContent className="bg-slate-900 border-white/10 text-white">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              Account Settings
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleUpdateProfile} className="space-y-4">
            <div>
              <Label htmlFor="profile-email">Email</Label>
              <Input
                id="profile-email"
                type="email"
                value={profileEmail}
                onChange={(e) => setProfileEmail(e.target.value)}
                className="bg-slate-800 border-white/20 text-white"
              />
            </div>
            <div className="border-t border-white/10 pt-4">
              <p className="text-white/70 text-sm mb-3">Change Password (leave blank to keep current)</p>
              <div className="space-y-3">
                <div>
                  <Label htmlFor="current-password">Current Password</Label>
                  <Input
                    id="current-password"
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="bg-slate-800 border-white/20 text-white"
                  />
                </div>
                <div>
                  <Label htmlFor="profile-new-password">New Password</Label>
                  <Input
                    id="profile-new-password"
                    type="password"
                    value={profileNewPassword}
                    onChange={(e) => setProfileNewPassword(e.target.value)}
                    className="bg-slate-800 border-white/20 text-white"
                  />
                </div>
              </div>
            </div>
            {profileMessage && (
              <p className={`text-sm ${profileMessage.includes('successfully') ? 'text-green-400' : 'text-red-400'}`}>
                {profileMessage}
              </p>
            )}
            <Button type="submit" className="w-full bg-purple-600 hover:bg-purple-700">
              Save Changes
            </Button>
            <div className="border-t border-white/10 pt-4">
              <Button
                type="button"
                variant="outline"
                className="w-full border-red-500/50 text-red-400 hover:bg-red-500/10"
                onClick={() => setShowDeleteConfirm(true)}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Account
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Account Confirmation */}
      <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
        <DialogContent className="bg-slate-900 border-white/10 text-white">
          <DialogHeader>
            <DialogTitle className="text-red-400">Delete Account</DialogTitle>
          </DialogHeader>
          <p className="text-white/70">Are you sure you want to delete your account? This action cannot be undone.</p>
          <div className="flex gap-3 mt-4">
            <Button variant="outline" className="flex-1 border-white/20 text-white" onClick={() => setShowDeleteConfirm(false)}>
              Cancel
            </Button>
            <Button className="flex-1 bg-red-600 hover:bg-red-700" onClick={handleDeleteAccount}>
              Delete Account
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Terms of Service Modal */}
      <Dialog open={showTerms} onOpenChange={setShowTerms}>
        <DialogContent className="bg-slate-900 border-white/10 text-white max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Terms of Service</DialogTitle>
          </DialogHeader>
          <div className="prose prose-invert prose-sm max-w-none">
            <p className="text-white/70">Last updated: January 2026</p>
            <h3 className="text-white">1. Acceptance of Terms</h3>
            <p className="text-white/70">By accessing and using PDFMagic, you accept and agree to be bound by these Terms of Service. If you do not agree to these terms, please do not use our service.</p>
            <h3 className="text-white">2. Description of Service</h3>
            <p className="text-white/70">PDFMagic provides online PDF processing tools including merging, splitting, compressing, and converting PDF files. We offer both free and paid subscription tiers.</p>
            <h3 className="text-white">3. User Accounts</h3>
            <p className="text-white/70">You are responsible for maintaining the confidentiality of your account credentials. You agree to notify us immediately of any unauthorized use of your account.</p>
            <h3 className="text-white">4. Acceptable Use</h3>
            <p className="text-white/70">You agree not to use PDFMagic for any unlawful purpose or to upload any content that violates applicable laws or third-party rights.</p>
            <h3 className="text-white">5. Payment Terms</h3>
            <p className="text-white/70">Paid subscriptions are billed monthly. You may cancel at any time, and your subscription will remain active until the end of the billing period.</p>
            <h3 className="text-white">6. Limitation of Liability</h3>
            <p className="text-white/70">PDFMagic is provided "as is" without warranties of any kind. We are not liable for any damages arising from your use of the service.</p>
            <h3 className="text-white">7. Changes to Terms</h3>
            <p className="text-white/70">We reserve the right to modify these terms at any time. Continued use of the service constitutes acceptance of modified terms.</p>
          </div>
        </DialogContent>
      </Dialog>

            {/* Privacy Policy Modal */}
            <Dialog open={showPrivacy} onOpenChange={setShowPrivacy}>
              <DialogContent className="bg-slate-900 border-white/10 text-white max-w-2xl max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Privacy Policy</DialogTitle>
                </DialogHeader>
                <div className="prose prose-invert prose-sm max-w-none">
                  <p className="text-white/70">Last updated: January 2026</p>
                  <h3 className="text-white">1. Information We Collect</h3>
                  <p className="text-white/70">We collect information you provide directly, including email address and payment information. We also collect usage data to improve our service.</p>
                  <h3 className="text-white">2. How We Use Your Information</h3>
                  <p className="text-white/70">We use your information to provide and improve our services, process payments, send service-related communications, and respond to your requests.</p>
                  <h3 className="text-white">3. File Processing</h3>
                  <p className="text-white/70">Files you upload are processed on our servers and are automatically deleted after processing. We do not store or access the contents of your files beyond what is necessary to provide the service.</p>
                  <h3 className="text-white">4. Data Security</h3>
                  <p className="text-white/70">We implement appropriate security measures to protect your personal information. However, no method of transmission over the Internet is 100% secure.</p>
                  <h3 className="text-white">5. Third-Party Services</h3>
                  <p className="text-white/70">We use third-party services for payment processing (Stripe) and authentication. These services have their own privacy policies.</p>
                  <h3 className="text-white">6. Your Rights</h3>
                  <p className="text-white/70">You have the right to access, correct, or delete your personal information. You can manage your account settings or contact us for assistance.</p>
                  <h3 className="text-white">7. Contact Us</h3>
                  <p className="text-white/70">If you have questions about this Privacy Policy, please contact us through our support channels.</p>
                </div>
              </DialogContent>
            </Dialog>

            {/* Analytics Dashboard Modal */}
            <Dialog open={showAnalytics} onOpenChange={setShowAnalytics}>
              <DialogContent className="bg-slate-900 border-white/10 text-white max-w-2xl">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5 text-purple-400" />
                    Analytics Dashboard
                  </DialogTitle>
                </DialogHeader>
                {analyticsData ? (
                  <div className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <Card className="bg-slate-800 border-white/10 p-4">
                        <p className="text-white/50 text-sm">Total Operations</p>
                        <p className="text-3xl font-bold text-white">{analyticsData.total_operations}</p>
                      </Card>
                      <Card className="bg-slate-800 border-white/10 p-4">
                        <p className="text-white/50 text-sm">Current Tier</p>
                        <p className="text-3xl font-bold text-purple-400">{analyticsData.tier.toUpperCase()}</p>
                      </Card>
                    </div>
              
                    <div>
                      <h4 className="text-white font-medium mb-3">Operations by Type</h4>
                      <div className="space-y-2">
                        {Object.entries(analyticsData.operations_by_type).length > 0 ? (
                          Object.entries(analyticsData.operations_by_type).map(([type, count]) => (
                            <div key={type} className="flex justify-between items-center bg-slate-800 rounded p-3">
                              <span className="text-white/70 capitalize">{type.replace('-', ' ')}</span>
                              <span className="text-white font-medium">{count}</span>
                            </div>
                          ))
                        ) : (
                          <p className="text-white/50 text-center py-4">No operations yet. Start processing PDFs!</p>
                        )}
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <Card className="bg-slate-800 border-white/10 p-4">
                        <p className="text-white/50 text-sm">Referred Users</p>
                        <p className="text-2xl font-bold text-white">{analyticsData.referred_users}</p>
                      </Card>
                      <Card className="bg-slate-800 border-white/10 p-4">
                        <p className="text-white/50 text-sm">Total Rewards</p>
                        <p className="text-2xl font-bold text-green-400">${analyticsData.total_rewards.toFixed(2)}</p>
                      </Card>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-white/50">Loading analytics...</p>
                  </div>
                )}
              </DialogContent>
            </Dialog>

            {/* Referral Program Modal */}
            <Dialog open={showReferral} onOpenChange={setShowReferral}>
              <DialogContent className="bg-slate-900 border-white/10 text-white max-w-lg">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Gift className="h-5 w-5 text-purple-400" />
                    Referral Program
                  </DialogTitle>
                </DialogHeader>
                {referralData ? (
                  <div className="space-y-6">
                    <div className="bg-gradient-to-r from-purple-900/50 to-pink-900/50 rounded-lg p-4 border border-purple-500/30">
                      <p className="text-white/70 text-sm mb-2">Share your referral link</p>
                      <div className="flex gap-2">
                        <Input
                          value={referralData.referral_url}
                          readOnly
                          className="bg-slate-800 border-white/20 text-white text-sm"
                        />
                        <Button onClick={copyReferralLink} className="bg-purple-600 hover:bg-purple-700">
                          {referralCopied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                        </Button>
                      </div>
                      <p className="text-white/50 text-xs mt-2">
                        Earn $0.50 for each signup and $1.00 for each conversion!
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <Card className="bg-slate-800 border-white/10 p-4 text-center">
                        <p className="text-white/50 text-sm">Referred Users</p>
                        <p className="text-3xl font-bold text-white">{referralData.referred_users}</p>
                      </Card>
                      <Card className="bg-slate-800 border-white/10 p-4 text-center">
                        <p className="text-white/50 text-sm">Converted</p>
                        <p className="text-3xl font-bold text-green-400">{referralData.converted_users}</p>
                      </Card>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <Card className="bg-slate-800 border-white/10 p-4 text-center">
                        <p className="text-white/50 text-sm">Total Earned</p>
                        <p className="text-2xl font-bold text-green-400">${referralData.total_rewards.toFixed(2)}</p>
                      </Card>
                      <Card className="bg-slate-800 border-white/10 p-4 text-center">
                        <p className="text-white/50 text-sm">Pending</p>
                        <p className="text-2xl font-bold text-yellow-400">${referralData.pending_rewards.toFixed(2)}</p>
                      </Card>
                    </div>

                    <div className="bg-slate-800 rounded-lg p-4">
                      <h4 className="text-white font-medium mb-2">How it works</h4>
                      <ul className="text-white/70 text-sm space-y-1">
                        <li>1. Share your unique referral link with friends</li>
                        <li>2. Earn $0.50 when they sign up</li>
                        <li>3. Earn $1.00 more when they upgrade to Pro or Business</li>
                        <li>4. Rewards are credited to your account monthly</li>
                      </ul>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-white/50">Loading referral data...</p>
                  </div>
                )}
              </DialogContent>
            </Dialog>

            {/* Footer */}
      <footer className="border-t border-white/10 bg-black/20 mt-16">
        <div className="container mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-white/50 text-sm">PDFMagic - Fast, secure PDF tools for everyone</p>
            <div className="flex gap-6 text-sm">
              <button onClick={() => setShowTerms(true)} className="text-white/50 hover:text-white transition-colors">
                Terms of Service
              </button>
              <button onClick={() => setShowPrivacy(true)} className="text-white/50 hover:text-white transition-colors">
                Privacy Policy
              </button>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}

export default App
