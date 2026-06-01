/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
  redirects: async () => [
    {
      source: '/',
      destination: '/auth/login',
      permanent: true,
    },
  ],
}

module.exports = nextConfig
