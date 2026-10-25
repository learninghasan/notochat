export default { async rewrites() { const backend=process.env.BACKEND_URL; return {beforeFiles:backend ? [{source:'/api/:path*',destination:`${backend.replace(/\/$/,'')}/:path*`}] : []}; } };
