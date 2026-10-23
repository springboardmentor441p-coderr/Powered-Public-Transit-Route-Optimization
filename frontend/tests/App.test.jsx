import React from 'react'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import App from '../src/App.jsx'

const tab = (name) => screen.getByRole('tab', { name })

describe('RouteRanker web app (against the live API)', () => {
  it('renders every tab with real data and no errors', async () => {
    const errors = vi.spyOn(console, 'error')
    render(<App />)
    await waitFor(() => expect(screen.getByText('Routes analysed')).toBeInTheDocument(), { timeout: 40000 })
    expect(await screen.findByText('Top 10 priority routes')).toBeInTheDocument()

    const steps = [['Explore', 'Busiest stops (bigger circle = more boardings)'], ['Clusters', 'Groups of similar routes'], ['Predictions', 'Route predictions'],
      ['Forecast', 'One route, with 80% range'], ['Recommendations', 'Recommended changes'], ['Impact', 'Current vs optimised service (weekday)'], ['Your data', 'Analyse your own bus feed']]
    for (const [name, text] of steps) {
      fireEvent.click(tab(name))
      expect(await screen.findByText(text, {}, { timeout: 40000 })).toBeInTheDocument()
      expect(screen.queryByText(/Something went wrong/)).toBeNull()
    }
    // forecast scenario switches the whole app
    fireEvent.click(screen.getByRole('button', { name: 'Next 12 months' }))
    fireEvent.click(tab('Recommendations'))
    await waitFor(() => expect(screen.getByText(/Route .* – /)).toBeInTheDocument(), { timeout: 40000 })
    // city filter
    fireEvent.click(screen.getByRole('button', { name: 'One' }))
    fireEvent.click(tab('Overview'))
    await waitFor(() => expect(screen.getByText('Cities').parentElement.textContent).toContain('1'), { timeout: 40000 })
    const bad = errors.mock.calls.filter((c) => !String(c[0]).includes('width(0)') && !String(c[0]).includes('act('))
    expect(bad.map((c) => String(c[0]).slice(0, 200))).toEqual([])
  })
})
