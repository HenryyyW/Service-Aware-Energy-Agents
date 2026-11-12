import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { CommunityCanvasPage } from '@/pages/CommunityCanvasPage'
import { api } from '@/api/client'
import { useNavigate } from 'react-router-dom'

vi.mock('@/api/client', () => ({
  api: {
    getRuns: vi.fn(),
    getScenario: vi.fn(),
    getTrajectories: vi.fn(),
  },
  wsManager: { on: vi.fn(), off: vi.fn(), send: vi.fn(), disconnect: vi.fn() },
}))

vi.mock('react-router-dom', async (importActual) => {
  const actual = await importActual<typeof import('react-router-dom')>()
  return {
    ...actual,
    useNavigate: vi.fn(() => vi.fn()),
  }
})

const mockApi = vi.mocked(api)
const mockNavigate = vi.mocked(useNavigate)

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  sessionStorage.clear()
})

describe('CommunityCanvasPage', () => {
  it('shows empty state when no runs exist', async () => {
    mockApi.getRuns.mockResolvedValue([])
    render(
      <MemoryRouter>
        <CommunityCanvasPage />
      </MemoryRouter>,
    )
    await screen.findByText(/no community data/i)
  })

  it('navigates to /scenarios from empty state browse button', async () => {
    mockApi.getRuns.mockResolvedValue([])
    mockNavigate.mockReturnValue(vi.fn())
    render(
      <MemoryRouter>
        <CommunityCanvasPage />
      </MemoryRouter>,
    )
    await screen.findByText(/no community data/i)
    const browseBtn = screen.getByRole('button', { name: /browse scenarios/i })
    fireEvent.click(browseBtn)
    expect(mockNavigate()).toHaveBeenCalledWith('/scenarios')
  })
})
