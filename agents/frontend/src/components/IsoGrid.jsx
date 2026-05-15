import { useMemo } from 'react'
import DeskCell from './DeskCell'
import { COLORS } from '../config/theme'

const GRID_SIZE = 5 // 5x5 = 25 cells; center is manager, 24 ring cells for sub-agents
const TILE_W = 120
const TILE_H = 60 // isometric tile aspect 2:1

/**
 * Top-down isometric office grid. Manager is pinned to the center cell;
 * sub-agents fill the ring around the manager (closest cells first, then
 * spiraling outward). Cells are depth-sorted so back tiles render first.
 */
export default function IsoGrid({ agents, manager, onCellClick }) {
  const cells = useMemo(() => buildCells(agents, manager), [agents, manager])

  // Grid bounding box (isometric coords):
  // x in [-(N-1)*TILE_W/2, +(N-1)*TILE_W/2]
  // y in [0, (2N-2)*TILE_H/2]
  const halfW = ((GRID_SIZE - 1) * TILE_W) / 2 + TILE_W / 2
  const totalH = (GRID_SIZE - 1) * TILE_H + TILE_H

  return (
    <div
      style={{
        position: 'relative',
        width: halfW * 2,
        height: totalH + 60, // extra room for name labels
        margin: '0 auto',
      }}
    >
      {/* subtle floor backdrop — a larger faded diamond behind the tiles */}
      <div
        style={{
          position: 'absolute',
          inset: '-30px',
          background: `radial-gradient(ellipse 60% 50% at 50% 55%, ${COLORS.bgCardSubtle} 0%, transparent 70%)`,
          pointerEvents: 'none',
        }}
      />

      {cells.map(({ row, col, agent, isManager, isEmpty, x, y }) => (
        <div
          key={`${row}-${col}`}
          style={{
            position: 'absolute',
            left: `${x + halfW - TILE_W / 2}px`,
            top: `${y}px`,
            zIndex: row + col,
            animation: agent && !isManager ? 'spawn-in 0.4s ease-out' : 'none',
          }}
        >
          <DeskCell
            agent={agent}
            isManager={isManager}
            isEmpty={isEmpty}
            onClick={agent && !isEmpty ? () => onCellClick?.(agent) : undefined}
          />
        </div>
      ))}
    </div>
  )
}

function buildCells(agents, manager) {
  const center = Math.floor(GRID_SIZE / 2)
  const subAgents = (agents || []).filter((a) => a.role !== 'manager').sort((a, b) => a.id - b.id)
  const positions = ringPositions(center)

  const cells = []
  for (let row = 0; row < GRID_SIZE; row++) {
    for (let col = 0; col < GRID_SIZE; col++) {
      const x = (col - row) * (TILE_W / 2)
      const y = (col + row) * (TILE_H / 2)
      const isCenter = row === center && col === center

      let agent = null
      let isManager = false
      let isEmpty = true

      if (isCenter && manager) {
        agent = manager
        isManager = true
        isEmpty = false
      } else if (!isCenter) {
        const ringIdx = positions.findIndex((p) => p.row === row && p.col === col)
        if (ringIdx >= 0 && ringIdx < subAgents.length) {
          agent = subAgents[ringIdx]
          isEmpty = false
        }
      }

      cells.push({ row, col, x, y, agent, isManager, isEmpty })
    }
  }

  // Depth-sort: back-most cells (smaller row+col) first so front cells overlap.
  cells.sort((a, b) => a.row + a.col - (b.row + b.col))
  return cells
}

/**
 * Ordered list of (row, col) cells excluding the center, sorted by
 * Chebyshev distance, then clockwise angle from north. This gives a
 * pleasant spiral fill as new agents are spawned.
 */
function ringPositions(center) {
  const cells = []
  for (let r = 0; r < GRID_SIZE; r++) {
    for (let c = 0; c < GRID_SIZE; c++) {
      const dr = r - center
      const dc = c - center
      if (dr === 0 && dc === 0) continue
      const dist = Math.max(Math.abs(dr), Math.abs(dc))
      // angle measured clockwise from "north" (negative dr direction)
      const angle = (Math.atan2(dc, -dr) + 2 * Math.PI) % (2 * Math.PI)
      cells.push({ row: r, col: c, dist, angle })
    }
  }
  cells.sort((a, b) => a.dist - b.dist || a.angle - b.angle)
  return cells
}
