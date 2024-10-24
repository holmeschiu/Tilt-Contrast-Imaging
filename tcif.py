#!/usr/bin/env python3
# TCIF (Q(p)). 
# Notes:
#   1. The image is presumed to be squared. 
#   2. Presumed the input specimen exit wave has the same dimension and pixel 
#      size as the TCIF. 

import cmath
import math
import numpy as np
import scipy as sp
import sys
from typing import Tuple


def wvlength_pm(kvolt: int) -> float:
    """Electron wavelength. 
    Args:
        kvolt (int): accelerating voltage in kV
    Returns:
        float: wavelength in pm
    """
    return 1.23e3 / cmath.sqrt(kvolt*1e3 * (1 + 9.78e-7*kvolt*1e3))


def aperture_inm(cutf_frequency_inm: float, imge_size: int, pxel_size_nm: float) -> np.ndarray:
    """Objective aperture function.  A 2D mask function.  The origin is in the image center. 
    Args:
        cutf_frequency_inm (float): cutoff frequency in nm^-1
        imge_size (int): image size in pixels
        pxel_size_nm (float): pixel size in nm/pixel 
    Returns:
        np.ndarray: a mask function for the aperture
    """
    start = np.zeros((imge_size, imge_size), dtype=float)
    
    if imge_size % 2 == 1:
        print("The image size should be even. ")
        sys.exit(0)
    else:
        cntr_shift_inm = imge_size / 2 / pxel_size_nm
        freq_step_inm = (1/pxel_size_nm) / imge_size

    for i in range(imge_size):
        for j in range(imge_size):
            if math.sqrt((i*freq_step_inm-cntr_shift_inm)**2 + (j*freq_step_inm-cntr_shift_inm)**2) < cutf_frequency_inm:
                start[i, j] = 1.0
            else:
                start[i, j] = 0.0

    return start


def W_0(Cs_mm: float, wvlength_pm: float, df1_nm: float, df2_nm: float, beta_0_rad: float, imge_size: int, pxel_size_nm: float) -> np.ndarray:
    """Phase distortion function in 2D.  The origin is in the center. 
       beta_0 is defined in Equation 5 in Cter paper (Penczek et al., 2014).
    Args:
        Cs_mm (float): spherical aberration in mm
        wvlength_pm (float): electron wavelength in pm
        df1_nm (float): defocus 1 in nm (long axis)
        df2_nm (float): defocus 2 in nm (short axis)
        beta_0_rad (float): angle between defocus 1 and x-axis in radian
        imge_size: image size in pixels
        pxel_size_nm: pixel size in nm
    Returns:
        np.ndarray: distorted phases in radian
    """
    start = np.zeros((imge_size, imge_size), dtype=float)

    freq_step_inm = (1/pxel_size_nm) / imge_size
    cntr_shift_inm = imge_size / 2 / pxel_size_nm
    za = (df1_nm + df2_nm) / 2
    zb = (df1_nm - df2_nm) / 2

    for i in range(imge_size):
        for j in range(imge_size):
            alpha_g = cmath.atan((j*freq_step_inm-cntr_shift_inm)/(i*freq_step_inm-cntr_shift_inm))
            ssqu = (i*freq_step_inm - cntr_shift_inm)**2 + (j*freq_step_inm - cntr_shift_inm)**2

            W1 = za + zb * cmath.cos(2*(alpha_g - beta_0_rad))
            W21 = -0.5 * W1 * wvlength_pm * ssqu * 1e-3
            W22 = 0.25 * Cs_mm * wvlength_pm**3 * ssqu**2 * 1e-3
            start[i, j] = start[i, j] + 6.28318 * (W21 + W22)

    return start

def calculate_spatial_frequencies(imge_size: int, pxel_size_nm: float):
    """Calculate frequency bins using np.fft.fftfreq and scale them with the pixel size (nm^-1)
    Args:
        imge_size (int):
        pxel_size_nm (float):
    Returns:
        freqs
    """
    # Frequencies in nm^-1
    freqs = np.fft.fftfreq(imge_size, d=pxel_size_nm)  
    # Shift frequencies to center the zero frequency
    freqs = np.fft.fftshift(freqs)  
    return freqs

def tcif(spec: np.ndarray, W_0: np.ndarray, beta_rad: float, alpha_rad: float, wvlength_pm: float, imge_size: int, pxel_size_nm: float):
    """Calculate TCIF in Fourier space. The origin is in the image center."""
    if (W_0.size != imge_size**2) or (spec.size != imge_size**2):
        print("The size of the phase array or the inputted exit wave does not match the image size.")
        sys.exit()

    amp = np.zeros((imge_size, imge_size), dtype=float)
    phs = np.zeros((imge_size, imge_size), dtype=float)

    # Calculate the spatial frequency grid (in nm^-1)
    freqs = calculate_spatial_frequencies(imge_size, pxel_size_nm)
    print('Spatial frequencies:', freqs)

    # Shifted FFT of the specimen exit wave
    f_spec = np.fft.fftshift(np.fft.fft2(spec))  
    # f_spec = np.fft.fft2(spec)
    print('f_spec', f_spec)

    # Ensure fill_value is compatible with the dtype of f_spec.real and f_spec.imag
    fill_value_real = np.float64(0.0)
    fill_value_imag = np.float64(0.0)

    # Set up interpolators for real and imaginary parts of the FFT of the specimen
    interpr = sp.interpolate.RegularGridInterpolator((freqs, freqs), f_spec.real, method='cubic', bounds_error=False, fill_value=fill_value_real)
    interpi = sp.interpolate.RegularGridInterpolator((freqs, freqs), f_spec.imag, method='cubic', bounds_error=False, fill_value=fill_value_imag)

    for i in range(imge_size):
        for j in range(imge_size):
            # sx and sy are now in the centered frequency grid
            sx = freqs[i]
            sy = freqs[j]
            print('sx:', sx, 'sy:', sy)
            ssqu = sx**2 + sy**2

            pnx_inm = sx - 0.5 * cmath.cos(beta_rad) * ssqu * wvlength_pm * cmath.tan(alpha_rad) * 1e-3
            # print('pnx_inm', pnx_inm)
            pny_inm = sy - 0.5 * cmath.sin(beta_rad) * ssqu * wvlength_pm * cmath.tan(alpha_rad) * 1e-3
            # print('pny_inm', pny_inm)
            ppx_inm = sx + 0.5 * cmath.cos(beta_rad) * ssqu * wvlength_pm * cmath.tan(alpha_rad) * 1e-3
            # print('ppx_inm', ppx_inm)
            ppy_inm = sy + 0.5 * cmath.sin(beta_rad) * ssqu * wvlength_pm * cmath.tan(alpha_rad) * 1e-3
            # print('ppy_inm', ppy_inm)

            # Interpolation on the input exit wave
            sp_rpn = interpr((pnx_inm.real, pny_inm.real))
            # print('sp_rpn', sp_rpn)
            sp_ipn = interpi((pnx_inm.real, pny_inm.real))
            # print('sp_ipn', sp_ipn)
            sp_rpp = interpr((ppx_inm.real, ppy_inm.real))
            # print('sp_rpp', sp_rpp)
            sp_ipp = interpi((ppx_inm.real, ppy_inm.real))
            # print('sp_ipp', sp_ipp)

            # Apply phase modulation
            phmod_cos = cmath.cos(W_0[i, j])
            phmod_sin = cmath.sin(W_0[i, j])
            
            Q1r = phmod_cos * sp_rpn + phmod_sin * sp_ipn
            Q1i = -phmod_sin * sp_rpn + phmod_cos * sp_ipn
            Q2r = phmod_cos * sp_rpp - phmod_sin * sp_ipp
            Q2i = phmod_sin * sp_rpp + phmod_cos * sp_ipp

            Q3r = -(Q1i - Q2i)
            Q3i = (Q1r - Q2r)

            amp[i, j] = amp[i, j] + cmath.sqrt(Q3r**2 + Q3i**2)
            phs[i, j] = phs[i, j] + cmath.atan(Q3i / Q3r)

    return amp, phs
            

def tcif_transform(amp: np.ndarray, phs: np.ndarray) -> np.ndarray:
    """Inverse Fourier transform of the tilt imaging function. 
    Args:
        amp (np.ndarray): amplitudes
        phs (np.ndarray): phases
    Returns:
        np.ndarray: intensities in real space
    """
    img_size = amp.shape[0]
    decom = np.zeros((img_size, img_size), dtype=complex) # used to be decom = np.zeros((img_size, img_size), dtype=float)

    for m in range(img_size):
        for n in range(img_size):
            decom[m, n] = amp[m, n] * (cmath.cos(phs[m, n]) + 1j * cmath.sin(phs[m, n]))

    return (np.fft.ifft(decom))**2
