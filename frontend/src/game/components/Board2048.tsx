import React, { useMemo } from 'react'
import { useGameStore } from '../hooks/useGameState'
import { extractTiles } from '../engine/Game2048'
import { TileCell } from './TileCell'

interface Board2048Props {
  boardSize: number   // px
  cellSize: number
  gap: number
}

export const Board2048: React.FC<Board2048Props> = ({ boardSize, cellSize, gap }) => {
  const grid = useGameStore(s => s.grid)
  const prevGrid = useGameStore(s => s.prevGrid)
  const lastMerged = useGameStore(s => s.lastMergedPositions)

  const tiles = useMemo(
    () => extractTiles(grid, prevGrid),
    [grid, prevGrid],
  )

  const gridCells = useMemo(() => {
    const cells: React.ReactNode[] = []
    for (let r = 0; r < 4; r++) {
      for (let c = 0; c < 4; c++) {
        cells.push(
          <div
            key={`bg-${r}-${c}`}
            style={{
              position: 'absolute',
              top: r * (cellSize + gap) + gap,
              left: c * (cellSize + gap) + gap,
              width: cellSize,
              height: cellSize,
              backgroundColor: 'rgba(238, 228, 218, 0.35)',
              borderRadius: 6,
            }}
          />,
        )
      }
    }
    return cells
  }, [cellSize, gap])

  return (
    <div
      role="grid"
      aria-label="2048 游戏面板"
      tabIndex={0}
      style={{
        position: 'relative',
        width: boardSize,
        height: boardSize,
        backgroundColor: '#bbada0',
        borderRadius: 10,
        margin: '0 auto',
        outline: 'none',
        touchAction: 'none',
      }}
    >
      {/* Background cells */}
      {gridCells}

      {/* Tiles */}
      {tiles.map(tile => (
        <TileCell
          key={tile.id}
          tile={tile}
          cellSize={cellSize}
          gap={gap}
          isMerged={lastMerged.has(`${tile.row},${tile.col}`)}
        />
      ))}
    </div>
  )
}
