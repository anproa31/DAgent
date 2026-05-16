import axios from 'axios'
import { useQuery } from '@tanstack/react-query'

const API_BASE_URL = import.meta.env.VITE_SERVER_URL || 'http://localhost:8000'

export interface TableInfo {
  name: string
  url: string
}

interface TableListResponse {
  table_count: number
  table_names: string[]
  message: string
}

const fetchTableList = async (): Promise<TableInfo[]> => {
  const response = await axios.get<TableListResponse>(
    `${API_BASE_URL}/api/get-table-list`
  )

  // Convert table_names to TableInfo format
  return response.data.table_names.map((tableName) => ({
    name: tableName,
    url: `/table/${tableName}`, // Generate URL using the table name
  }))
}

export const useTableList = () => {
  return useQuery({
    queryKey: ['tableList'],
    queryFn: fetchTableList,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    refetchOnWindowFocus: false,
  })
}
