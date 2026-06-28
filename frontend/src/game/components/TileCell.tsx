import React from 'react'
import type { Tile as TileType } from '../types'
import { getTileColor, getTileFontSize } from '../config'

interface TileCellProps {
  tile: TileType
  cellSize: number
  gap: number
  isMerged: boolean
}

export const TileCell: React.FC<TileCellProps> = React.memo(({ tile, cellSize, gap, isMerged }) => {
  const colors = getTileColor(tile.value)
  const fontSize = getTileFontSize(tile.value, cellSize)

  return (
    <div
      style={{
        position: 'absolute',
        top: tile.row * (cellSize + gap) + gap,
        left: tile.col * (cellSize + gap) + gap,
        width: cellSize,
        height: cellSize,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: colors.bg,
        color: colors.text,
        fontSize,
        fontWeight: 700,
        borderRadius: 6,
        zIndex: tile.value > 0 ? 1 : 0,
        transform: isMerged ? 'scale(1.1)' : tile.isNew ? 'scale(0)' : 'scale(1)',
        transition: 'top 0.15s ease, left 0.15s ease, transform 0.15s ease',
        animation: isMerged ? 'tilePop 0.2s ease-out' : tile.isNew ? 'tileAppear 0.15s ease-out forwards' : 'none',
        boxShadow: tile.value >= 128 ? '0 0 10px rgba(0,0,0,0.2)' : 'none',
        userSelect: 'none',
      }}
    >
      {tile.value > 0 ? tile.value : ''}
    </div>
  )
})

TileCell.displayName = 'TileCell'
