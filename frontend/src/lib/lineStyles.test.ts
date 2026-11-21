import { describe, expect, it } from 'vitest'
import { ROUTE_DASHES, routeDashes } from './lineStyles'

describe('routeDashes', () => {
  it('first route solid, second dashed', () => {
    expect(routeDashes(['120', '121'])).toEqual({ '120': null, '121': '10 7' })
  })
  it('up to 8 routes all get different patterns', () => {
    const d = routeDashes(['1', '2', '3', '4', '5', '6', '7', '8'])
    expect(new Set(Object.values(d)).size).toBe(8)
    expect(ROUTE_DASHES).toHaveLength(8)
  })
})
