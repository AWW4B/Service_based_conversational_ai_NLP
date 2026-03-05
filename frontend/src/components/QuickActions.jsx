import { motion } from 'framer-motion';
import { Flame, Smartphone, Cpu, Shirt, Laptop } from 'lucide-react';

const quickActions = [
    { label: 'Best Deals', icon: Flame, query: 'Show me the best deals today' },
    { label: 'Phones', icon: Smartphone, query: 'I want to buy a phone' },
    { label: 'Electronics', icon: Cpu, query: 'Show me popular electronics' },
    { label: 'Fashion', icon: Shirt, query: 'I want to explore fashion items' },
    { label: 'Laptops', icon: Laptop, query: 'I need a laptop' },
];

export default function QuickActions({ onSelect, disabled }) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.4 }}
            className="flex flex-wrap gap-2 px-4 pb-3"
        >
            {quickActions.map(({ label, icon: Icon, query }) => (
                <motion.button
                    key={label}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    disabled={disabled}
                    onClick={() => onSelect(query)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-full text-xs font-medium text-gray-700 hover:border-[#F57224] hover:text-[#F57224] hover:shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    <Icon size={14} />
                    {label}
                </motion.button>
            ))}
        </motion.div>
    );
}
