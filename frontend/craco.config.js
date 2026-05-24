// frontend/craco.config.js

const path = require("path");
module.exports = {
    // Disable ESLint during webpack builds for faster builds
    eslint: {
        enable: false,
        mode: 'file',
    },
    // Disable TypeScript checking during build (faster builds)
    typescript: {
        enableTypeChecking: false,
    },
    style: {
        postcssOptions: {
            plugins: [
                require('tailwindcss'),
                require('autoprefixer'),
            ],
        },
    },
    webpack: {
        alias: {
            // ... (Your existing aliases)
            // CRITICAL FIX: FORCES REDIRECTION of the illegal path to the correct file location
            '../../theme': path.resolve(__dirname, 'src/theme'), 
            
            '@': path.resolve(__dirname, 'src'),
            '@components': path.resolve(__dirname, 'src/components'),
            '@hooks': path.resolve(__dirname, 'src/hooks'),
            '@contexts': path.resolve(__dirname, 'src/contexts'),
            '@utils': path.resolve(__dirname, 'src/utils'),
            '@styles': path.resolve(__dirname, 'src/styles'),
            '@assets': path.resolve(__dirname, 'src/assets'),
            '@lib': path.resolve(__dirname, 'src/lib'),
            '@pages': path.resolve(__dirname, 'src/pages'),
            '@types': path.resolve(__dirname, 'src/types'),
            '#components': path.resolve(__dirname, 'src/components'),
            '#hooks': path.resolve(__dirname, 'src/hooks'),
            '#utils': path.resolve(__dirname, 'src/utils'),
            '#contexts': path.resolve(__dirname, 'src/contexts'),
        },
        configure: (webpackConfig, { paths }) => { 
            
            // --- CRITICAL FIX START: Allow Webpack to process files outside of src/ ---
            const oneOfRule = webpackConfig.module.rules.find(rule => rule.oneOf);

            if (oneOfRule) {
                // Find the rule that uses babel-loader and includes files from 'paths.appSrc'
                const jsRule = oneOfRule.oneOf.find(
                  rule => rule.loader && rule.loader.includes('babel-loader')
                );

                if (jsRule) {
                    // Add paths that include the parent directories to the rule's `include` list.
                    // This is the secondary fix that complements the alias above.
                    jsRule.include = Array.isArray(jsRule.include)
                        ? [...jsRule.include, path.resolve(__dirname, '..'), path.resolve(__dirname, '../..')]
                        : [jsRule.include, path.resolve(__dirname, '..'), path.resolve(__dirname, '../..')];
                }
            }
            // --- CRITICAL FIX END ---

            // Clean up source maps in production to save space
            if (process.env.NODE_ENV === 'production') {
                webpackConfig.devtool = false;
            }
            // Performance hints
            webpackConfig.performance = {
                hints: false,
                maxAssetSize: 512000,
                maxEntrypointSize: 512000, 
            };
            return webpackConfig;
        },
    },
    devServer: {
        port: parseInt(process.env.PORT || '3000', 10),
        hot: true,
        open: true,
        historyApiFallback: true,
        proxy: {
            '/api': {
                target: process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001',
                changeOrigin: true,
                secure: false,
                pathRewrite: {
                    '^/api': ''
                },
            },
        },
    },
};