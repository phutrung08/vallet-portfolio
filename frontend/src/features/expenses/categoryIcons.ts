import type { Component } from 'vue'
import { BedDouble, Car, Receipt, ShoppingBag, Soup, Ticket } from 'lucide-vue-next'
import type { ExpenseCategory } from '@/entities'

export const categoryIcons: Record<ExpenseCategory, Component> = {
  food: Soup,
  transport: Car,
  lodging: BedDouble,
  activity: Ticket,
  shopping: ShoppingBag,
  other: Receipt,
}
