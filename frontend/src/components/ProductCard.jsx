import { motion } from 'framer-motion';
import { Star, ExternalLink } from 'lucide-react';

export default function ProductCard({ product }) {
    const { name, price, rating, image, url } = product;

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            whileHover={{ scale: 1.02, y: -2 }}
            transition={{ duration: 0.2 }}
            className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden w-52 shrink-0 cursor-pointer hover:shadow-md transition-shadow"
        >
            {/* Product image */}
            <div className="h-36 bg-gray-50 flex items-center justify-center overflow-hidden">
                <img
                    src={image || 'https://placehold.co/200x150/f5f5f5/999?text=Product'}
                    alt={name}
                    className="h-full w-full object-contain p-2"
                    onError={(e) => {
                        e.target.src = 'https://placehold.co/200x150/f5f5f5/999?text=Product';
                    }}
                />
            </div>

            {/* Info */}
            <div className="p-3 space-y-1.5">
                <h4 className="text-sm font-semibold text-gray-800 line-clamp-2 leading-snug">
                    {name}
                </h4>

                <p className="text-base font-bold text-[#F57224]">
                    Rs. {price?.toLocaleString?.() || price}
                </p>

                {/* Rating */}
                {rating && (
                    <div className="flex items-center gap-1">
                        {Array.from({ length: 5 }).map((_, i) => (
                            <Star
                                key={i}
                                size={12}
                                className={i < Math.round(rating) ? 'text-yellow-400 fill-yellow-400' : 'text-gray-300'}
                            />
                        ))}
                        <span className="text-xs text-gray-500 ml-1">{rating}</span>
                    </div>
                )}

                {/* CTA */}
                <a
                    href={url || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 flex items-center justify-center gap-1.5 w-full py-1.5 bg-[#F57224] hover:bg-[#e0621a] text-white text-xs font-semibold rounded-lg transition-colors"
                >
                    View Product <ExternalLink size={12} />
                </a>
            </div>
        </motion.div>
    );
}
