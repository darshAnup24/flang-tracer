! C01: Whole-array assignment
! This is the fundamental array operation in Fortran.
program array_assign
    implicit none
    integer, dimension(5) :: A, B, C
    
    ! Initialize arrays
    B = [1, 2, 3, 4, 5]
    C = [10, 20, 30, 40, 50]
    
    ! The construct below will be traced
    A(:) = B(:) + C(:)
    
    print *, A
end program array_assign
