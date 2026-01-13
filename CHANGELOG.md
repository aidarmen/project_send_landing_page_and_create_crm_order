# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-01-08

### Added
- **Bilingual Support (Russian/Kazakh)**: Full bilingual support for landing page
  - Language toggle button in navigation (switches between RU/KK)
  - Cookie-based language preference persistence (1 year expiration)
  - URL parameter support (`?lang=kk` or `?lang=ru`)
  - Default language: Russian
- **Kazakh Translations for Product Offers**:
  - Kazakh title field for product offers in admin panel
  - Kazakh title fields for all component types (Internet, TV, Mobile, Home Phone, SIM Devices)
  - Kazakh badges field in admin panel
  - Automatic fallback to Russian when Kazakh translations are missing
- **Translation System**:
  - New `translations.py` module with comprehensive Russian and Kazakh translations
  - All UI text translated (buttons, labels, terms, footer)
  - Service type names translated
  - Component labels and descriptions translated
- **Customer Information Display**:
  - Display customer account ID (лицевой счет) on landing page
  - Display customer address (town_name, street_name, house, flat) on landing page
  - Readable address format instead of IDs
- **Version Tracking**:
  - Version tracking system with VERSION file
  - Version display on admin dashboard
  - Version display in admin panel footer
  - `/api/version` endpoint for API access
  - Version logging on application startup

### Changed
- **Address Fields**: Updated to use readable address fields (town_name, street_name) instead of street_id
  - Required fields: `street_name`, `house`
  - Optional fields: `town_name`, `sub_house`, `flat`, `zip_code`, `street_id` (for API compatibility)
- **Landing Page**: 
  - Modified to show personalized customer information
  - Updated to support bilingual content with language switching
  - Dynamic language attribute in HTML tag
  - Translated meta tags and page titles
- **Admin Panel**:
  - Added Kazakh translation fields for offers, components, and badges
  - Updated offer form to include bilingual input fields
  - Enhanced translation storage in offer details_json

### Technical Details
- Translation structure: `details.translations = {"ru": {...}, "kk": {...}}`
- Component translations stored with type mapping for efficient lookup
- Fallback logic: Kazakh → Russian → Original value
- Cookie name: `landing_lang` with 1 year expiration

## [1.0.0] - 2026-01-08

### Added
- Display customer account ID (лицевой счет) on landing page
- Display customer address on landing page
- Version tracking system with VERSION file
- CHANGELOG.md for tracking project updates

### Changed
- Modified landing page to show personalized customer information
- Updated landing route to fetch and pass customer data to template

