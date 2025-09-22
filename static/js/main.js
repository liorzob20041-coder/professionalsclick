// Main JavaScript for ProfessionalsClick

// Language switcher
function changeLanguage(newLang) {
    const currentPath = window.location.pathname;
    const pathParts = currentPath.split('/');
    
    // Replace or add language code
    if (pathParts[1] && (pathParts[1] === 'he' || pathParts[1] === 'en' || pathParts[1] === 'ru')) {
        pathParts[1] = newLang;
    } else {
        pathParts.splice(1, 0, newLang);
    }
    
    const newPath = pathParts.join('/');
    window.location.href = newPath;
}

// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function() {
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    const navLinks = document.querySelector('.nav-links');
    
    if (mobileMenuToggle && navLinks) {
        mobileMenuToggle.addEventListener('click', function() {
            navLinks.classList.toggle('active');
            this.classList.toggle('active');
        });
    }
    
    // Search functionality
    const searchForm = document.querySelector('.search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const profession = document.getElementById('profession').value;
            const city = document.getElementById('city').value;
            
            if (profession || city) {
                let searchUrl = '/he/professionals';
                const params = new URLSearchParams();
                
                if (profession) params.append('category', profession);
                if (city) params.append('city', city);
                
                if (params.toString()) {
                    searchUrl += '?' + params.toString();
                }
                
                window.location.href = searchUrl;
            }
        });
    }
    
    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.style.borderColor = '#e74c3c';
                } else {
                    field.style.borderColor = '#e9ecef';
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                alert('אנא מלא את כל השדות הנדרשים');
            }
        });
    });
    
    // Phone number formatting
    const phoneInputs = document.querySelectorAll('input[type="tel"]');
    phoneInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\D/g, '');
            if (value.startsWith('972')) {
                value = '0' + value.substring(3);
            }
            
            // Format Israeli phone number
            if (value.length >= 10) {
                value = value.substring(0, 3) + '-' + value.substring(3, 10);
            }
            
            e.target.value = value;
        });
    });
    
    // Professional card interactions
    const professionalCards = document.querySelectorAll('.professional-card');
    professionalCards.forEach(card => {
        card.addEventListener('click', function(e) {
            if (!e.target.closest('.btn')) {
                const profileLink = card.querySelector('a[href*="/professional/"]');
                if (profileLink) {
                    window.location.href = profileLink.href;
                }
            }
        });
    });
    
    // Smooth scrolling for anchor links
    const anchorLinks = document.querySelectorAll('a[href^="#"]');
    anchorLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const targetId = this.getAttribute('href').substring(1);
            const targetElement = document.getElementById(targetId);
            
            if (targetElement) {
                targetElement.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
});

// Star rating display
function displayStars(rating, maxStars = 5) {
    let stars = '';
    for (let i = 1; i <= maxStars; i++) {
        if (i <= rating) {
            stars += '★';
        } else if (i - 0.5 <= rating) {
            stars += '½';
        } else {
            stars += '☆';
        }
    }
    return stars;
}

// Format phone number for display
function formatPhoneNumber(phone) {
    const cleaned = phone.replace(/\D/g, '');
    if (cleaned.length === 10 && cleaned.startsWith('0')) {
        return cleaned.substring(0, 3) + '-' + cleaned.substring(3, 10);
    }
    return phone;
}

// Copy to clipboard functionality
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        alert('הטלפון הועתק ללוח');
    }).catch(function() {
        console.error('Failed to copy to clipboard');
    });
}