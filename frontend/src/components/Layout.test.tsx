import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Layout from './Layout'

vi.mock('react-router-dom', async (importActual) => {
  const actual = await importActual<typeof import('react-router-dom')>()
  return {
    ...actual,
    useLocation: vi.fn(() => ({ pathname: '/scenarios/generate' })),
  }
})

describe('Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the page title and the mobile hamburger button', () => {
    render(
      <MemoryRouter initialEntries={['/scenarios/generate']}>
        <Layout />
      </MemoryRouter>,
    )
    expect(screen.getByText(/Generate/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /toggle menu/i })).toBeInTheDocument()
  })

  it('toggles the sidebar open/closed on hamburger click', () => {
    render(
      <MemoryRouter initialEntries={['/scenarios/generate']}>
        <Layout />
      </MemoryRouter>,
    )
    const sidebar = document.querySelector('.sidebar')!
    const btn = screen.getByRole('button', { name: /toggle menu/i })
    expect(sidebar.className).not.toContain('open')
    fireEvent.click(btn)
    expect(sidebar.className).toContain('open')
    fireEvent.click(btn)
    expect(sidebar.className).not.toContain('open')
  })
})
