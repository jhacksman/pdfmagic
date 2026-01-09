# PDFMagic

A full-stack PDF tools SaaS application with user authentication, subscription billing via Stripe, and multiple PDF processing capabilities.

## Features

- **PDF Merge** - Combine multiple PDF files into one
- **PDF Split** - Split a PDF into individual pages
- **PDF Compress** - Reduce PDF file size
- **PDF to Images** - Extract images from PDF files
- **Images to PDF** - Convert images to PDF format

## Tech Stack

### Backend
- FastAPI (Python)
- SQLite with persistent storage
- JWT authentication
- Stripe integration for subscriptions
- PyPDF2 for PDF processing
- Pillow for image processing

### Frontend
- React + TypeScript
- Vite build tool
- Tailwind CSS
- shadcn/ui components
- Lucide icons

## Pricing Tiers

| Tier | Price | Daily Operations | Max File Size |
|------|-------|------------------|---------------|
| Free | $0 | 3 | 5MB |
| Pro | $9.99/mo | 1,000 | 50MB |
| Business | $24.99/mo | 10,000 | 100MB |

## Setup

### Backend

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Install dependencies:
   ```bash
   poetry install
   ```

3. Create a `.env` file with the following variables:
   ```
   JWT_SECRET_KEY=your-secret-key-here
   STRIPE_SECRET_KEY=sk_live_xxx
   STRIPE_WEBHOOK_SECRET=whsec_xxx
   STRIPE_PRICE_PRO=price_xxx
   STRIPE_PRICE_BUSINESS=price_xxx
   DATABASE_PATH=/data/app.db
   FRONTEND_URL=https://your-frontend-url.com
   ```

4. Run the development server:
   ```bash
   poetry run fastapi dev app/main.py
   ```

### Frontend

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create a `.env` file:
   ```
   VITE_API_URL=http://localhost:8000
   ```

4. Run the development server:
   ```bash
   npm run dev
   ```

5. Build for production:
   ```bash
   npm run build
   ```

## Stripe Configuration

To enable payments, you need to:

1. Create a Stripe account at https://stripe.com
2. Create two subscription products with prices:
   - Pro: $9.99/month
   - Business: $24.99/month
3. Copy the price IDs to your backend `.env` file
4. Set up a webhook endpoint pointing to `/api/stripe/webhook`
5. Configure the webhook to listen for:
   - `checkout.session.completed`
   - `customer.subscription.deleted`

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register a new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/user/me` - Get current user info

### PDF Operations
- `POST /api/pdf/merge` - Merge multiple PDFs
- `POST /api/pdf/split` - Split PDF into pages
- `POST /api/pdf/compress` - Compress PDF
- `POST /api/pdf/to-images` - Extract images from PDF
- `POST /api/images/to-pdf` - Convert images to PDF

### Stripe
- `POST /api/stripe/create-checkout` - Create checkout session
- `POST /api/stripe/webhook` - Handle Stripe webhooks
- `POST /api/stripe/portal` - Get billing portal URL
- `GET /api/pricing` - Get pricing information

## License

MIT
