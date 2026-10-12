import { describe, expect, it } from 'vitest'

import { createApiClient } from './client'

describe('createApiClient', () => {
  it('returns a stub client shape with no network calls', () => {
    const client = createApiClient()

    expect(client).toEqual({ baseUrl: '' })
  })
})
