# PDFMagic Cost Analysis

This document analyzes the operational costs of running PDFMagic and compares them against the subscription pricing tiers.

## PDF Processing Technology

PDFMagic uses **open-source Python libraries** for all PDF operations:

- **PyPDF2**: PDF merge, split, compress, and page extraction
- **Pillow (PIL)**: Image processing for PDF-to-images and images-to-PDF

These libraries run locally on the server with **zero per-operation API costs**. This is fundamentally different from AI-based services (like OpenAI, AWS Textract, or Adobe PDF Services) that charge per API call.

## Infrastructure Costs (Fly.io)

### Compute (Monthly)

| Configuration | Cost/Month |
|---------------|------------|
| Shared CPU 1x 256MB | ~$1.94 |
| Shared CPU 1x 512MB | ~$3.88 |
| Shared CPU 1x 1GB | ~$5.70 |
| Shared CPU 2x 2GB | ~$20.37 |

Current deployment uses Shared CPU 1x with 1GB RAM.

### Storage

| Resource | Cost |
|----------|------|
| Persistent Volume | $0.15/GB/month |
| Volume Snapshots | $0.08/GB/month (first 10GB free) |

Current deployment uses 1GB volume = $0.15/month.

### Bandwidth

| Tier | Included | Overage |
|------|----------|---------|
| Free allowance | 160GB/month | - |
| Additional | - | ~$0.02/GB (varies by region) |

### Estimated Base Infrastructure Cost

| Component | Monthly Cost |
|-----------|--------------|
| Compute (Shared 1x 1GB) | $5.70 |
| Storage (1GB Volume) | $0.15 |
| Bandwidth | $0 (within free tier) |
| **Total** | **~$6/month** |

## Per-Operation Cost Analysis

Since PyPDF2 and Pillow are local libraries with no API fees, the per-operation cost is effectively **$0** for processing. The only variable costs are:

1. **CPU time**: Already covered by monthly hosting fee
2. **Bandwidth**: Upload + download of files

### Bandwidth per Operation

| Scenario | Upload | Download | Total |
|----------|--------|----------|-------|
| Small PDF (1MB) | 1MB | 1MB | 2MB |
| Medium PDF (5MB) | 5MB | 5MB | 10MB |
| Large PDF (50MB) | 50MB | 50MB | 100MB |

### Pro Tier Bandwidth Analysis (1,000 ops/day)

Assuming average 2MB per operation (upload + download):
- Daily: 1,000 ops x 2MB = 2GB
- Monthly: 2GB x 30 = 60GB
- **Within 160GB free tier**

### Business Tier Bandwidth Analysis (10,000 ops/day)

Assuming average 2MB per operation:
- Daily: 10,000 ops x 2MB = 20GB
- Monthly: 20GB x 30 = 600GB
- Overage: 600GB - 160GB = 440GB
- **Additional cost: ~$8.80/month** (at $0.02/GB)

## Pricing Tier Profitability

### Assumptions
- Base infrastructure: $6/month (shared across all users)
- Infrastructure scales with users (add more compute as needed)
- Estimated infrastructure cost per active user: ~$0.50-1.00/month at scale

### Per-User Profit Margins

| Tier | Price | Est. Cost/User | Profit/User | Margin |
|------|-------|----------------|-------------|--------|
| Free | $0 | $0.10 | -$0.10 | N/A |
| Pro | $9.99 | $0.50-1.00 | $9.00-9.50 | 90-95% |
| Business | $24.99 | $1.00-2.00 | $23.00-24.00 | 92-96% |

### Scaling Economics

| Users | Monthly Revenue | Est. Infrastructure | Profit | Margin |
|-------|-----------------|---------------------|--------|--------|
| 10 Pro | $99.90 | $10 | $89.90 | 90% |
| 100 Pro | $999 | $30 | $969 | 97% |
| 1,000 Pro | $9,990 | $150 | $9,840 | 98% |

## Comparison: API-Based vs Local Processing

If PDFMagic used cloud PDF APIs instead:

### Adobe PDF Services API
- $0.05 per PDF operation
- 1,000 ops/day = $50/day = **$1,500/month per Pro user**

### AWS Textract
- $1.50 per 1,000 pages
- Varies significantly by document complexity

### iLovePDF API
- $0.01-0.05 per operation
- 1,000 ops/day = $10-50/day = **$300-1,500/month per Pro user**

**Conclusion**: Using local open-source libraries (PyPDF2, Pillow) instead of cloud APIs saves $300-1,500+ per Pro user per month.

## Key Findings

1. **Zero API costs**: PyPDF2 and Pillow are free, open-source libraries with no per-operation charges.

2. **High margins**: 90-98% profit margins at scale due to local processing.

3. **Scalable infrastructure**: Fly.io allows scaling compute as needed, with costs growing sub-linearly with users.

4. **Bandwidth is the main variable cost**: Heavy users may exceed the 160GB free tier, but overage costs are minimal (~$0.02/GB).

5. **Pro tier is profitable**: Even with 1,000 operations/day, the infrastructure cost per user is well under $1/month.

6. **Business tier is highly profitable**: The $24.99 price point provides excellent margins even for heavy users.

## Recommendations

1. **Current pricing is sustainable**: The Pro ($9.99) and Business ($24.99) tiers are profitable at any scale.

2. **Monitor bandwidth usage**: Implement bandwidth tracking to identify heavy users who may need rate limiting.

3. **Consider compute scaling**: As user base grows, upgrade to Performance CPUs or add more Machines.

4. **Free tier limits are appropriate**: 3 ops/day and 5MB file size limits prevent abuse while allowing users to try the service.

## References

- Fly.io Pricing: https://fly.io/docs/about/pricing/
- PyPDF2 (MIT License): https://pypdf2.readthedocs.io/
- Pillow (HPND License): https://pillow.readthedocs.io/
- Adobe PDF Services Pricing: https://developer.adobe.com/document-services/pricing/
