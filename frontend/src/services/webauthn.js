import api from './api'

// Helper to convert base64url to ArrayBuffer
function base64urlToBuffer(base64url) {
  const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/')
  const pad = base64.length % 4 === 0 ? '' : '='.repeat(4 - (base64.length % 4))
  const binary = atob(base64 + pad)
  return Uint8Array.from(binary, c => c.charCodeAt(0)).buffer
}

// Helper to convert ArrayBuffer to base64url
function bufferToBase64url(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  bytes.forEach(b => binary += String.fromCharCode(b))
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')
}

export async function startRegistration() {
  const res = await api('/api/auth/webauthn/register/begin', { method: 'POST' })
  if (!res.ok) throw new Error('Failed to start registration')
  const options = await res.json()

  // Convert base64url strings to ArrayBuffers for WebAuthn API
  options.challenge = base64urlToBuffer(options.challenge)
  options.user.id = base64urlToBuffer(options.user.id)
  if (options.excludeCredentials) {
    options.excludeCredentials = options.excludeCredentials.map(c => ({
      ...c,
      id: base64urlToBuffer(c.id),
    }))
  }

  const credential = await navigator.credentials.create({ publicKey: options })

  // Convert response to JSON-serializable format
  const response = {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    response: {
      attestationObject: bufferToBase64url(credential.response.attestationObject),
      clientDataJSON: bufferToBase64url(credential.response.clientDataJSON),
    },
  }

  const verifyRes = await api('/api/auth/webauthn/register/complete', {
    method: 'POST',
    body: JSON.stringify(response),
  })
  if (!verifyRes.ok) throw new Error('Registration verification failed')
  return verifyRes.json()
}

export async function startAuthentication() {
  const res = await api('/api/auth/webauthn/login/begin', { method: 'POST' })
  if (!res.ok) throw new Error('Failed to start authentication')
  const options = await res.json()

  options.challenge = base64urlToBuffer(options.challenge)
  if (options.allowCredentials) {
    options.allowCredentials = options.allowCredentials.map(c => ({
      ...c,
      id: base64urlToBuffer(c.id),
    }))
  }

  const assertion = await navigator.credentials.get({ publicKey: options })

  const response = {
    id: assertion.id,
    rawId: bufferToBase64url(assertion.rawId),
    type: assertion.type,
    response: {
      authenticatorData: bufferToBase64url(assertion.response.authenticatorData),
      clientDataJSON: bufferToBase64url(assertion.response.clientDataJSON),
      signature: bufferToBase64url(assertion.response.signature),
      userHandle: assertion.response.userHandle ? bufferToBase64url(assertion.response.userHandle) : null,
    },
  }

  const verifyRes = await api('/api/auth/webauthn/login/complete', {
    method: 'POST',
    body: JSON.stringify(response),
  })
  if (!verifyRes.ok) throw new Error('Authentication failed')
  return verifyRes.json()
}

export async function getCredentials() {
  const res = await api('/api/auth/webauthn/credentials')
  return res.json()
}

export async function deleteCredential(id) {
  const res = await api(`/api/auth/webauthn/credentials/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete credential')
  return res.json()
}
