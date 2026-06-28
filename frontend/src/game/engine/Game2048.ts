// Pure 2048 Game Engine — no React dependency, fully testable

import type { Grid, Tile, Direction, MoveResult } from '../types'

let _tileId = 0
function nextId(): number { return ++_tileId }

/** 深拷贝棋盘 */
function cloneGrid(g: Grid): Grid {
  return g.map(row => [...row])
}

/** 创建空棋盘 */
export function createEmptyGrid(size: number): Grid {
  return Array.from({ length: size }, () => Array(size).fill(0))
}

/** 随机添加一个瓦片 (2 90%, 4 10%) */
export function addRandomTile(grid: Grid, rng: () => number = Math.random): Grid | null {
  const empty: [number, number][] = []
  for (let r = 0; r < grid.length; r++) {
    for (let c = 0; c < grid[r].length; c++) {
      if (grid[r][c] === 0) empty.push([r, c])
    }
  }
  if (empty.length === 0) return null
  const [r, c] = empty[Math.floor(rng() * empty.length)]
  const newGrid = cloneGrid(grid)
  newGrid[r][c] = rng() < 0.9 ? 2 : 4
  return newGrid
}

/** 将行向左挤压合并 */
function slideRow(row: number[]): { newRow: number[]; score: number; merged: number[] } {
  // 去零
  let arr = row.filter(v => v !== 0)
  let score = 0
  const merged: number[] = []

  for (let i = 0; i < arr.length - 1; i++) {
    if (arr[i] === arr[i + 1]) {
      arr[i] *= 2
      score += arr[i]
      merged.push(i)
      arr[i + 1] = 0
      i++ // skip the zero
    }
  }

  arr = arr.filter(v => v !== 0)
  while (arr.length < row.length) arr.push(0)
  return { newRow: arr, score, merged }
}

/** 执行一次移动，返回新棋盘和结果 */
export function move(
  grid: Grid,
  direction: Direction,
): { grid: Grid; result: MoveResult } {
  const size = grid.length
  let totalScore = 0
  const mergedCells: { row: number; col: number; value: number }[] = []
  const newGrid = createEmptyGrid(size)

  for (let i = 0; i < size; i++) {
    let row: number[]
    switch (direction) {
      case 'left':
        row = grid[i]
        break
      case 'right':
        row = [...grid[i]].reverse()
        break
      case 'up':
        row = grid.map(r => r[i])
        break
      case 'down':
        row = grid.map(r => r[i]).reverse()
        break
    }

    const { newRow, score, merged } = slideRow(row)
    totalScore += score

    for (const mIdx of merged) {
      const val = newRow[mIdx]
      let realRow: number, realCol: number
      switch (direction) {
        case 'left':  realRow = i; realCol = mIdx; break
        case 'right': realRow = i; realCol = size - 1 - mIdx; break
        case 'up':    realRow = mIdx; realCol = i; break
        case 'down':  realRow = size - 1 - mIdx; realCol = i; break
      }
      mergedCells.push({ row: realRow, col: realCol, value: val })
    }

    const restoredRow = direction === 'right' || direction === 'down'
      ? [...newRow].reverse()
      : newRow

    if (direction === 'left' || direction === 'right') {
      newGrid[i] = restoredRow
    } else {
      for (let r = 0; r < size; r++) {
        newGrid[r][i] = restoredRow[r]
      }
    }
  }

  const moved = !gridsEqual(grid, newGrid)
  return { grid: newGrid, result: { moved, scoreGained: totalScore, mergedTiles: mergedCells } }
}

/** 比较两个棋盘是否相等 */
function gridsEqual(a: Grid, b: Grid): boolean {
  for (let r = 0; r < a.length; r++) {
    for (let c = 0; c < a[r].length; c++) {
      if (a[r][c] !== b[r][c]) return false
    }
  }
  return true
}

/** 检查是否有可用移动 */
export function hasAvailableMoves(grid: Grid): boolean {
  const size = grid.length
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      if (grid[r][c] === 0) return true
      if (c < size - 1 && grid[r][c] === grid[r][c + 1]) return true
      if (r < size - 1 && grid[r][c] === grid[r + 1][c]) return true
    }
  }
  return false
}

/** 获取棋盘最大瓦片 */
export function getMaxTile(grid: Grid): number {
  let max = 0
  for (const row of grid) {
    for (const cell of row) {
      if (cell > max) max = cell
    }
  }
  return max
}

/** 提取所有瓦片为 Tile 对象数组 */
export function extractTiles(grid: Grid, prevGrid: Grid | null): Tile[] {
  const tiles: Tile[] = []
  for (let r = 0; r < grid.length; r++) {
    for (let c = 0; c < grid[r].length; c++) {
      if (grid[r][c] !== 0) {
        const isNew = prevGrid !== null && prevGrid[r][c] === 0
        tiles.push({
          id: nextId(),
          value: grid[r][c],
          row: r,
          col: c,
          merged: false,
          isNew,
        })
      }
    }
  }
  return tiles
}

/** 初始化新游戏棋盘 */
export function initGame(size: number, startTiles: number, rng?: () => number): Grid {
  _tileId = 0
  let grid = createEmptyGrid(size)
  for (let i = 0; i < startTiles; i++) {
    const next = addRandomTile(grid, rng)
    if (next) grid = next
  }
  return grid
}
