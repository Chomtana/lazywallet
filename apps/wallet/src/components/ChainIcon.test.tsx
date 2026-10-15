import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ChainIcon } from './ChainIcon'

afterEach(cleanup)

describe('ChainIcon', () => {
  it('draws the known chains with an accessible name', () => {
    render(<ChainIcon network="Ethereum" />)
    render(<ChainIcon network="avalanche" />)
    expect(screen.getByRole('img', { name: 'Ethereum' }).tagName.toLowerCase()).toBe('svg')
    expect(screen.getByRole('img', { name: 'Avalanche' }).tagName.toLowerCase()).toBe('svg')
  })

  it('falls back to a muted initials circle for an unknown network', () => {
    render(<ChainIcon network="Base" size={20} />)
    const icon = screen.getByRole('img', { name: 'Base' })
    expect(icon.tagName.toLowerCase()).toBe('span')
    expect(icon.textContent).toBe('BA')
    expect(icon.style.width).toBe('20px')
  })
})
