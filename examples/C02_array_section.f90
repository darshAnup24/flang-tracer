! C02: Array section with stride
program array_section
    implicit none
    integer, dimension(10) :: A, B
    B = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    
    ! The construct below will be traced
    A(1:10:2) = B(1:5)
end program array_section
