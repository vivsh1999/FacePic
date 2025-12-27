import { Context, Next } from 'hono'

export const ADMIN_PASSWORD = 'admin123'

export const adminAuth = async (c: Context, next: Next) => {
  const authHeader = c.req.header('X-Admin-Password')
  
  if (authHeader === ADMIN_PASSWORD) {
    await next()
  } else {
    return c.json({ error: 'Unauthorized' }, 401)
  }
}
